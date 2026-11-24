import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.exporter import build_ffmpeg_command  # noqa: E402


def test_command_reads_raw_frames_and_source_audio_into_vertical_mp4():
    cmd = build_ffmpeg_command("ffmpeg", Path("in.mp4"), 12.5, 20.0, 30.0, Path("out.mp4"))
    assert cmd[0] == "ffmpeg"
    assert "1080x1920" in cmd                    # output size
    assert cmd[cmd.index("-i") + 1] == "pipe:0"  # video frames come from Python
    assert "in.mp4" in cmd                       # audio comes from the source
    assert cmd[cmd.index("-ss") + 1] == "12.500"
    assert cmd[cmd.index("-t") + 1] == "20.000"
    assert cmd[-1] == "out.mp4"


def test_command_is_a_list_so_no_shell_injection_is_possible():
    cmd = build_ffmpeg_command("ffmpeg", Path("a; rm -rf x.mp4"), 0, 5, 25, Path("o.mp4"))
    assert all(isinstance(part, str) for part in cmd)
    assert "a; rm -rf x.mp4" in cmd  # passed as one argument, never parsed by a shell
