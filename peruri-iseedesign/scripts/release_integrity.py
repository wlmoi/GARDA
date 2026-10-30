"""Read Git symlinks consistently on native and core.symlinks=false checkouts."""
import os


def read_symlink_payload(path):
    """Hash the link target, not its referent or its platform-specific file type.

    Git stores symlinks as mode 120000 blobs containing the target path. Windows
    with core.symlinks=false checks out that same blob as an ordinary text file.
    Native symlinks may refer to directories or may be dangling; neither needs
    to be followed to validate the recorded link.
    """
    if path.is_symlink():
        return os.readlink(path).encode('utf-8', errors='surrogateescape')
    return path.read_bytes()
