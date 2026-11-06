from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.agents.base import BaseAgent
from app.config import GENERATED_DIR


def _sanitize_filename(value: str) -> str:
    """Return a filesystem-safe, stable filename component."""
    cleaned = str(value or "")
    cleaned = cleaned.strip()
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", "", cleaned)
    cleaned = re.sub(r"[\\/:*?\"<>|.]+", "_", cleaned)
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip("_")
    return cleaned or "campaign"


def sanitize_filename(value: str, max_length: int = 80) -> str:
    """Return a filesystem-safe, stable filename component."""
    cleaned = _sanitize_filename(value)
    return cleaned[:max_length].strip("_") or "campaign"


def _escape_drawtext(value: str) -> str:
    """Escape ffmpeg drawtext special characters instead of injecting them."""
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    escaped = escaped.replace(":", "\\:").replace("%", "\\%")
    escaped = escaped.replace(",", "\\,").replace("[", "\\[").replace("]", "\\]")
    return escaped.replace("\n", " ").replace("\r", " ")


def _srt_timestamp(seconds: float) -> str:
    total_ms = int(round(max(0.0, seconds) * 1000))
    hours, remainder = divmod(total_ms // 1000, 3600)
    minutes, secs = divmod(remainder, 60)
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _load_font(size: int):
    for font_name in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _video_dimensions(platform: str) -> tuple[int, int]:
    if platform == "Instagram":
        return (1080, 1920)  # vertical 9:16
    if platform == "YouTube":
        return (1280, 720)  # landscape 16:9
    return (1280, 720)


class VideoProductionAgent(BaseAgent):
    name = "Video Production Agent"

    MIN_WORDS_FOR_TARGET_DURATION = 110
    TARGET_MIN_SECONDS = 60
    TARGET_MAX_SECONDS = 90
    SEGMENT_PAUSE_SECONDS = 0.7

    @staticmethod
    def _find_ffmpeg() -> str | None:
        configured = os.getenv("FFMPEG_BINARY", "").strip()
        if configured:
            return configured
        discovered = shutil.which("ffmpeg")
        if discovered:
            return discovered
        for candidate in (
            r"D:\ffmpeg\bin\ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            "/usr/local/bin/ffmpeg",
            "/usr/bin/ffmpeg",
        ):
            if Path(candidate).is_file():
                return candidate
        return None

    @staticmethod
    def _find_ffprobe() -> str | None:
        configured = os.getenv("FFPROBE_BINARY", "").strip()
        if configured:
            return configured
        ffmpeg = VideoProductionAgent._find_ffmpeg()
        if ffmpeg:
            candidate = Path(ffmpeg).with_name("ffprobe.exe")
            if candidate.is_file():
                return str(candidate)
        discovered = shutil.which("ffprobe")
        if discovered:
            return discovered
        return None

    @staticmethod
    def _split_script(script: str) -> list[str]:
        """Split narration text into readable, speakable segments."""
        text = re.sub(r"\s+", " ", str(script or "").strip())
        if not text:
            return []
        raw_sentences = re.split(r"(?<=[.!?])\s+", text)
        segments: list[str] = []
        buffer = ""
        for sentence in raw_sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) > 120:
                # Split very long sentences on commas so captions stay readable.
                pieces = [p.strip() for p in sentence.split(",") if p.strip()]
                for piece in pieces:
                    chunk = f"{piece}."
                    if len(chunk) > 240:
                        chunk = chunk[:237].rstrip() + "."
                    segments.append(chunk)
                continue
            if buffer and len(buffer) + len(sentence) + 1 <= 110:
                buffer = f"{buffer} {sentence}"
            else:
                if buffer:
                    segments.append(buffer)
                buffer = sentence
        if buffer:
            segments.append(buffer)
        return segments

    # Running pyttsx3 in-process on Windows deadlocks after the first
    # save_to_file()/runAndWait() cycle (SAPI COM event loop never unwinds),
    # so synthesis always runs in a short-lived child process with a hard
    # timeout that the parent terminates if it gets stuck.
    TTS_SUBPROCESS_TIMEOUT_SECONDS = 90.0
    TTS_SPEECH_RATE = 170

    @staticmethod
    def _tts_child_main(narration_text: str, wav_path: str, rate: int) -> None:
        """Entry point for the isolated TTS child process.

        Writes exactly one complete WAV file for the whole narration. Any
        failure exits non-zero so the parent treats the result as failed.
        """
        import wave

        import pyttsx3

        engine = pyttsx3.init()
        wav_file: wave.Wave_write | None = None
        try:
            engine.setProperty("rate", rate)
            engine.save_to_file(narration_text, wav_path)
            engine.runAndWait()
            if not os.path.exists(wav_path) or os.path.getsize(wav_path) == 0:
                raise RuntimeError("pyttsx3 produced no audio output.")
            with wave.open(wav_path, "rb") as handle:
                frames = handle.getnframes()
                rate_hz = handle.getframerate() or 0
            if frames <= 0 or rate_hz <= 0 or (frames / float(rate_hz)) < 0.05:
                raise RuntimeError("pyttsx3 produced an empty or invalid WAV file.")
        finally:
            try:
                engine.stop()
            except Exception:
                pass

    def _synthesize_narration(self, segments: list[str], work_dir: Path) -> tuple[Path, float]:
        """Render the complete narration to ONE WAV file using offline pyttsx3.

        pyttsx3 deadlocks on Windows when save_to_file()/runAndWait() are used
        more than once per process, so synthesis runs in an isolated child
        process that the parent terminates on timeout. Returns
        (wav_path, duration_seconds) and raises on any failure so callers can
        fall back to a silent render instead of reporting fake narration.
        """
        narration_text = " ".join(str(segment).strip() for segment in segments if str(segment).strip())
        if not narration_text:
            raise RuntimeError("No narration text was supplied for synthesis.")

        wav_path = work_dir / "narration.wav"
        temp_wav_path = work_dir / f"narration_{os.getpid()}_{int(time.time() * 1000)}.wav.tmp"

        # Remove any stale outputs so a failed run cannot leave a previous
        # narration file behind and look successful.
        wav_path.unlink(missing_ok=True)
        temp_wav_path.unlink(missing_ok=True)

        command = [
            sys.executable,
            "-c",
            (
                "import sys;"
                "from app.agents.video_production_agent import VideoProductionAgent;"
                "VideoProductionAgent._tts_child_main(sys.argv[1], sys.argv[2], int(sys.argv[3]))"
            ),
            narration_text,
            str(temp_wav_path),
            str(self.TTS_SPEECH_RATE),
        ]

        env = os.environ.copy()
        env.setdefault("PYTHONPATH", str(Path(__file__).resolve().parents[1]))
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            _stdout_data, stderr_data = process.communicate(timeout=self.TTS_SUBPROCESS_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.communicate(timeout=10)
            temp_wav_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Offline TTS synthesis timed out after {self.TTS_SUBPROCESS_TIMEOUT_SECONDS:.0f}s and was terminated."
            ) from exc

        if process.returncode != 0:
            temp_wav_path.unlink(missing_ok=True)
            detail = (stderr_data or "").strip().splitlines()
            detail = detail[-1] if detail else f"exit code {process.returncode}"
            raise RuntimeError(f"Offline TTS synthesis failed: {detail}")

        if not temp_wav_path.exists() or temp_wav_path.stat().st_size == 0:
            temp_wav_path.unlink(missing_ok=True)
            raise RuntimeError("Offline TTS synthesis produced no audio output.")

        duration = self._wav_duration(temp_wav_path)
        if duration <= 0.05:
            temp_wav_path.unlink(missing_ok=True)
            raise RuntimeError("Offline TTS synthesis produced an empty narration track.")

        # Move the validated result into place atomically so there is exactly
        # one narration file and no temporary leftovers.
        os.replace(temp_wav_path, wav_path)
        return wav_path, duration

    @staticmethod
    def _wav_duration(path: Path) -> float:
        """Return the duration of a WAV file in seconds."""
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate() or 1
        return frames / float(rate)

    @staticmethod
    def _estimate_scene_timings_from_duration(
        scene_texts: list[str],
        total_duration: float,
        pause_seconds: float,
    ) -> list[tuple[float, float]]:
        """Estimate subtitle timings across the real narration duration.

        These are length-weighted estimates, not word-level speech
        recognition: each caption's share of the narration is proportional to
        its character length. Timing stays aligned with the audio because the
        total matches the measured narration duration.
        """
        if not scene_texts:
            return []
        lengths = [max(1, len(str(text))) for text in scene_texts]
        total_length = sum(lengths)
        total_speech = max(0.1, total_duration - pause_seconds * max(0, len(scene_texts) - 1))

        timings: list[tuple[float, float]] = []
        cursor = 0.0
        for index, length in enumerate(lengths):
            share = (length / total_length) * total_speech
            start = cursor
            end = cursor + share
            timings.append((start, end))
            cursor = end + (pause_seconds if index < len(scene_texts) - 1 else 0.0)
        return timings

    def _build_scene_image(
        self,
        index: int,
        total_scenes: int,
        segment_text: str,
        title: str,
        platform: str,
        width: int,
        height: int,
        accent: tuple[int, int, int],
    ) -> Image.Image:
        """Create one visually distinct campaign scene with Pillow."""
        image = Image.new("RGB", (width, height), color=(13, 18, 32))
        draw = ImageDraw.Draw(image)

        # Background gradient with per-scene rotation so scenes differ.
        gradient_dark = (13, 18, 32)
        gradient_light = tuple(min(255, channel + 34 + (index % 3) * 12) for channel in accent)
        for y in range(height):
            ratio = y / max(height - 1, 1)
            wave_shift = (index % 4) / 4.0
            adjusted = min(1.0, max(0.0, ratio * 0.9 + wave_shift * 0.1))
            color = tuple(
                int(gradient_dark[c] * (1 - adjusted) + gradient_light[c] * adjusted)
                for c in range(3)
            )
            draw.line((0, y, width, y), fill=color)

        # Distinct graphic motif per scene index (rotating through 4 styles).
        motif = index % 4
        if motif == 0:  # progress bars
            for bar_index in range(4):
                bar_width = int((width * 0.7) * ((bar_index + index % 3 + 1) / 6))
                draw.rounded_rectangle(
                    (80, height - 420 + bar_index * 70, 80 + bar_width, height - 380 + bar_index * 70),
                    radius=18,
                    fill=accent,
                )
        elif motif == 1:  # circles
            for circle_index in range(5):
                radius = 40 + circle_index * 26
                draw.ellipse(
                    (width - 260 - circle_index * 8, height - 260 - circle_index * 8,
                     width - 260 + circle_index * 8, height - 260 + circle_index * 8),
                    outline=accent,
                    width=6,
                )
        elif motif == 2:  # vertical stripes
            for stripe_index in range(6):
                x = 80 + stripe_index * 64
                draw.rectangle((x, height - 420, x + 26, height - 160), fill=accent)
        else:  # diagonal frame accents
            draw.line((60, height - 180, width - 60, height - 480), fill=accent, width=10)
            draw.line((60, height - 120, width - 60, height - 420), fill=(255, 255, 255), width=4)

        # Header: campaign title chip.
        title_font = _load_font(58)
        small_font = _load_font(34)
        caption_font = _load_font(52)

        draw.rounded_rectangle((60, 90, width - 60, 220), radius=28, fill=(10, 14, 26))
        draw.text((100, 120), platform.upper(), fill=accent, font=small_font)
        draw.text((100, 165), title[:52], fill=(255, 255, 255), font=title_font)

        # Scene narration text, word-wrapped.
        words = segment_text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if caption_font.getlength(candidate) > width - 200:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        lines = lines[:6]

        text_top = int(height * 0.46)
        for line_index, line in enumerate(lines):
            draw.text((100, text_top + line_index * 72), line, fill=(244, 246, 255), font=caption_font)

        # Scene counter.
        draw.text((100, height - 260), f"Scene {index + 1}/{total_scenes}", fill=(200, 212, 240), font=small_font)
        draw.rectangle((0, height - 24, width, height), fill=accent)
        return image

    def _build_srt(self, subtitle_path: Path, captions: list[str], timings: list[tuple[float, float]] | None = None) -> None:
        """Write an SRT file; when narration timings exist they are used so subtitles stay synchronized."""
        lines = []
        for index, caption in enumerate(captions, start=1):
            if timings and index - 1 < len(timings):
                start, end = timings[index - 1]
            else:
                start = (index - 1) * 2
                end = index * 2
            lines.append(
                f"{index}\n"
                f"{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n"
                f"{caption}\n"
            )
        subtitle_path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _accent_color(platform: str) -> tuple[int, int, int]:
        if platform == "Instagram":
            return (139, 92, 246)
        if platform == "YouTube":
            return (34, 211, 238)
        return (16, 185, 129)

    def _build_thumbnail(self, title: str, platform: str, thumbnail_path: Path, width: int | None = None, height: int | None = None) -> None:
        if width is None or height is None:
            width, height = _video_dimensions(platform)
        accent = self._accent_color(platform)
        image = Image.new("RGB", (width, height), color=(17, 24, 39))
        draw = ImageDraw.Draw(image)

        for y in range(height):
            ratio = y / max(height - 1, 1)
            color = tuple(
                int((17, 24, 39)[channel] * (1 - ratio) + accent[channel] * ratio)
                for channel in range(3)
            )
            draw.line((0, y, width, y), fill=color)

        draw.rounded_rectangle((60, 60, width - 60, height - 60), radius=36, outline=(255, 255, 255), width=3)
        draw.rectangle((80, height - 220, width - 80, height - 140), fill=accent)

        title_font = _load_font(56 if width >= 1000 else 40)
        small_font = _load_font(30 if width >= 1000 else 22)
        draw.text((120, 150), platform.upper(), fill=(230, 240, 255), font=small_font)
        draw.text((120, 220), title[:60], fill=(255, 255, 255), font=title_font)
        draw.text((120, height - 200), "Creator-approved video thumbnail", fill=(17, 24, 39), font=small_font)
        image.save(thumbnail_path)

    def _build_fallback_video(self, title: str, platform: str, video_path: Path) -> None:
        """Create an animated GIF when ffmpeg is unavailable.

        The fallback keeps the pipeline usable offline while clearly reporting
        the render engine in the agent response.
        """
        width, height = 960, 540
        accent = self._accent_color(platform)
        title_font = _load_font(40)
        small_font = _load_font(24)
        frames = []

        for frame_index in range(8):
            image = Image.new("RGB", (width, height), color=(17, 24, 39))
            draw = ImageDraw.Draw(image)
            bar_width = int((width - 120) * ((frame_index + 1) / 8))
            draw.rectangle((60, height - 110, 60 + bar_width, height - 70), fill=accent)
            draw.rectangle((60, 60, width - 60, height - 60), outline=(80, 95, 130), width=3)
            draw.text((90, 120), platform.upper(), fill=(200, 220, 255), font=small_font)
            draw.text((90, 200), title[:48], fill=(255, 255, 255), font=title_font)
            draw.text((90, height - 170), "Offline preview render", fill=(190, 205, 230), font=small_font)
            frames.append(image)

        frames[0].save(
            video_path,
            save_all=True,
            append_images=frames[1:],
            duration=450,
            loop=0,
        )

    def _render_mp4(self, ffmpeg: str, title: str, platform: str, video_path: Path) -> None:
        """Legacy single-slide render kept for backward compatibility."""
        accent = self._accent_color(platform)
        color = "0x{:02x}{:02x}{:02x}".format(*accent)
        safe_title = _escape_drawtext(title)
        temp_path = video_path.with_name(f"{video_path.stem}.tmp{video_path.suffix}")

        command = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x111827:s=1280x720:d=6",
            "-vf",
            (
                f"drawtext=text='{safe_title}':fontcolor=white:fontsize=42:"
                f"x=(w-text_w)/2:y=(h-text_h)/2,"
                f"drawbox=x=40:y=580:w=1200:h=100:color={color}@0.75:t=fill"
            ),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(temp_path),
        ]

        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
            temp_path.replace(video_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def _render_scenes_mp4(
        self,
        ffmpeg: str,
        scene_paths: list[Path],
        scene_durations: list[float],
        audio_path: Path | None,
        video_path: Path,
    ) -> None:
        """Encode one H.264 MP4 from the generated scene stills plus narration."""
        if not scene_paths:
            raise RuntimeError("No scene frames were generated.")
        temp_path = video_path.with_name(f"{video_path.stem}.tmp{video_path.suffix}")

        inputs: list[str] = []
        for scene_path, duration in zip(scene_paths, scene_durations):
            inputs.extend(["-loop", "1", "-t", f"{duration:.3f}", "-i", str(scene_path)])

        filter_parts = []
        for index in range(len(scene_paths)):
            filter_parts.append(f"[{index}:v]scale=iw:ih,setsar=1[v{index}]")
        concat_inputs = "".join(f"[v{index}]" for index in range(len(scene_paths)))
        filter_parts.append(f"{concat_inputs}concat=n={len(scene_paths)}:v=1:a=0,format=yuv420p[vout]")

        audio_index = len(scene_paths)
        command = [ffmpeg, "-y", *inputs]
        if audio_path is not None:
            command.extend(["-i", str(audio_path)])
            filter_parts.append(f"[{audio_index}:a]anull[aout]")
            command.extend(["-map", "[vout]", "-map", "[aout]"])
            command.extend(["-c:a", "aac", "-b:a", "128k", "-shortest"])
        else:
            command.extend(["-map", "[vout]"])

        command.extend(
            [
                "-filter_complex",
                ";".join(filter_parts),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "21",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(temp_path),
            ]
        )

        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)
            temp_path.replace(video_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def execute(
        self,
        title: str,
        script: str,
        platform: str = "Instagram",
        captions: list[str] | None = None,
        content: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        self.status = "running"
        started_at = self._now()
        output_dir = GENERATED_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = _sanitize_filename(f"{platform.lower()}_{title.lower().replace(' ', '_')[:30]}")
        requested_video_path = output_dir / f"{base_name}.mp4"
        thumbnail_path = output_dir / f"{base_name}_thumb.png"
        subtitle_path = output_dir / f"{base_name}.srt"

        narration_text = str(script or content or title or "").strip()
        segments = self._split_script(narration_text)
        if captions:
            # Prefer meaningful script segments; captions act as scene labels only
            # when the script itself is too short to drive the timeline.
            pass

        width, height = _video_dimensions(platform)
        accent = self._accent_color(platform)

        video_path = output_dir / f"{base_name}.gif"
        video_format = "gif"
        render_engine = "pillow"
        render_error: str | None = None
        audio_enabled = False
        duration_seconds = 0.0
        segment_timings: list[tuple[float, float]] = []
        scene_count = 0
        tts_error: str | None = None

        word_count = len(re.findall(r"\b\w+\b", narration_text))
        script_sufficient = word_count >= self.MIN_WORDS_FOR_TARGET_DURATION

        scene_texts = segments if segments else [title or "Creator video"]
        if not segments and captions:
            scene_texts = list(captions)

        ffmpeg = self._find_ffmpeg()
        narration_audio: Path | None = None

        if ffmpeg and narration_text:
            # 1) Offline narration: ONE complete WAV synthesized in an isolated
            # subprocess (repeated in-process pyttsx3 calls deadlock on Windows).
            try:
                narration_audio, narration_duration = self._synthesize_narration(scene_texts, output_dir)
                audio_enabled = True
                # Subtitle/scene timings are length-weighted estimates across
                # the real narration duration; they are not speech recognition.
                segment_timings = self._estimate_scene_timings_from_duration(
                    scene_texts, narration_duration, self.SEGMENT_PAUSE_SECONDS
                )
                scene_durations = [
                    (end - start) + (self.SEGMENT_PAUSE_SECONDS if index < len(segment_timings) - 1 else 0.0)
                    for index, (start, end) in enumerate(segment_timings)
                ]
                duration_seconds = sum(scene_durations)
            except Exception as exc:  # noqa: BLE001 - TTS is optional
                tts_error = str(exc)
                narration_audio = None
                audio_enabled = False

        if not audio_enabled:
            # Honest fallback timing: each scene gets a fixed readable duration,
            # no artificial padding, no fake narration.
            scene_durations = [max(2.5, min(4.0, len(text.split()) * 0.45 + 1.8)) for text in scene_texts]
            duration_seconds = sum(scene_durations)
            cumulative = 0.0
            for duration in scene_durations:
                segment_timings.append((cumulative, cumulative + duration))
                cumulative += duration

        if ffmpeg:
            try:
                scene_paths: list[Path] = []
                for index, scene_text in enumerate(scene_texts):
                    scene_path = output_dir / f"{base_name}_scene_{index:03d}.png"
                    image = self._build_scene_image(
                        index=index,
                        total_scenes=len(scene_texts),
                        segment_text=scene_text,
                        title=title or "Creator video",
                        platform=platform,
                        width=width,
                        height=height,
                        accent=accent,
                    )
                    image.save(scene_path)
                    scene_paths.append(scene_path)
                scene_count = len(scene_paths)

                self._render_scenes_mp4(
                    ffmpeg,
                    scene_paths,
                    scene_durations,
                    narration_audio,
                    requested_video_path,
                )
                video_path = requested_video_path
                video_format = "mp4"
                render_engine = "ffmpeg"
            except Exception as exc:  # noqa: BLE001 - degrade to offline render
                render_error = str(exc)
                render_engine = "pillow"

        if render_engine == "pillow":
            self._build_fallback_video(title, platform, video_path)
            video_format = "gif"

        self._build_thumbnail(title, platform, thumbnail_path, width, height)

        # Synchronized subtitles: narration timings when available.
        subtitle_texts = scene_texts if segments else (captions or scene_texts)
        self._build_srt(subtitle_path, subtitle_texts, segment_timings if segment_timings else None)
        # Preserve the legacy response contract: "captions" echoes the
        # supplied caption list when one was provided.
        response_captions = captions if captions else subtitle_texts

        self.status = "completed"
        limits = (
            "Offline narration and template-based motion graphics; no unauthorized face or voice cloning. "
            f"Render engine: {render_engine}."
        )
        if render_error:
            limits += " ffmpeg failed, so an offline animated preview was generated instead."
        if tts_error:
            limits += f" Offline TTS narration failed ({tts_error}); video rendered without voice-over."
        if not script_sufficient and narration_text:
            limits += (
                f" Supplied script is only {word_count} words, so the narration runs about "
                f"{duration_seconds:.0f}s instead of the 60-90s target; nothing was padded with filler."
            )

        media_urls = {
            "video_url": f"/generated/{video_path.name}" if video_path.exists() else None,
            "thumbnail_url": f"/generated/{thumbnail_path.name}" if thumbnail_path.exists() else None,
            "subtitle_url": f"/generated/{subtitle_path.name}" if subtitle_path.exists() else None,
        }

        return {
            "agent": self.name,
            "status": self.status,
            "started_at": started_at,
            "completed_at": self._now(),
            "platform": platform,
            "video_path": str(video_path),
            "video_format": video_format,
            "render_engine": render_engine,
            "render_error": render_error,
            "thumbnail_path": str(thumbnail_path),
            "subtitle_path": str(subtitle_path),
            "captions": response_captions,
            "limits": limits,
            # New, backward-compatible extensions:
            "duration_seconds": round(duration_seconds, 2),
            "audio_enabled": audio_enabled,
            "scene_count": scene_count,
            "video_width": width,
            "video_height": height,
            "script_sufficient": script_sufficient,
            "word_count": word_count,
            "tts_error": tts_error,
            "narration_audio_path": str(narration_audio) if narration_audio else None,
            **media_urls,
        }
