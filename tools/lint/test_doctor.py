"""The doctor must name a sync client before it costs someone a session.

A working copy inside iCloud, Dropbox, OneDrive or Google Drive is raced by
the sync client: gates fail on a tree nobody touched. Attendees clone
wherever they happen to be, so the tool says so at setup time rather than
leaving it to be discovered as a mysterious red gate mid-session.
"""

from tools.lint import doctor


def test_paths_inside_a_sync_root_are_named(tmp_path):
    home = tmp_path / "home"
    cases = {
        "Library/Mobile Documents/com~apple~CloudDocs/work/repo": "iCloud Drive",
        "Dropbox/repo": "Dropbox",
        "OneDrive/repo": "OneDrive",
        "OneDrive - Acme Corp/repo": "OneDrive",
        "Google Drive/My Drive/repo": "Google Drive",
        "Library/CloudStorage/GoogleDrive-me@example.com/repo": "Google Drive",
        "Library/CloudStorage/Dropbox/repo": "Dropbox",
    }
    for rel, expected in cases.items():
        path = home / rel
        path.mkdir(parents=True, exist_ok=True)
        found = doctor.sync_client_owning(path, home)
        assert found is not None, rel
        assert expected.split()[0] in found, f"{rel}: got {found}"


def test_an_ordinary_path_is_not_flagged(tmp_path):
    home = tmp_path / "home"
    path = home / "src" / "repo"
    path.mkdir(parents=True)
    assert doctor.sync_client_owning(path, home) is None


def test_macos_desktop_redirect_is_detected(tmp_path):
    """Desktop and Documents sync leaves the path looking ordinary while the
    bytes live in CloudDocs, which is exactly how it goes unnoticed."""
    home = tmp_path / "home"
    (home / "Library/Mobile Documents/com~apple~CloudDocs/Desktop").mkdir(parents=True)
    repo = home / "Desktop" / "Projects" / "repo"
    repo.mkdir(parents=True)
    found = doctor.sync_client_owning(repo, home)
    assert found is not None and "iCloud" in found


def test_desktop_without_the_redirect_is_not_flagged(tmp_path):
    home = tmp_path / "home"
    repo = home / "Desktop" / "repo"
    repo.mkdir(parents=True)
    assert doctor.sync_client_owning(repo, home) is None


def test_the_warning_never_fails_the_doctor(tmp_path, capsys):
    """It is the user's machine and their choice, so this is a warning."""
    home = tmp_path / "home"
    repo = home / "Dropbox" / "repo"
    repo.mkdir(parents=True)
    assert doctor.sync_client_owning(repo, home) == "Dropbox"
