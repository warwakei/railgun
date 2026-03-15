#!/usr/bin/env python3
import subprocess
import sys
import os
import platform
import urllib.request
import zipfile
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress
    import questionary
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings
except ImportError:
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "rich", "questionary", "prompt-toolkit", "-q"])
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress
    import questionary
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings

console = Console()

ALPINE_FILENAME = "alpine-minirootfs-3.23.3-aarch64.tar.gz"
ALPINE_URL = "https://dl-cdn.alpinelinux.org/alpine/v3.23/releases/aarch64/alpine-minirootfs-3.23.3-aarch64.tar.gz"
CHROOT_PATH = "/data/local/tmp/alpine"
SETUP_FLAG = "alpineJustInstalled"
DNS_SERVER = "8.8.8.8"
ALPINE_REPOS = [
    "http://dl-cdn.alpinelinux.org/alpine/v3.23/main",
    "http://dl-cdn.alpinelinux.org/alpine/v3.23/community",
    "http://dl-cdn.alpinelinux.org/alpine/edge/main",
    "http://dl-cdn.alpinelinux.org/alpine/edge/community",
]
RAILGUN_REPO_URL = "https://raw.githubusercontent.com/warwakei/railgun/main/apps"

@dataclass
class App:
    name: str
    package: str
    app_type: str

class Railgun:
    def __init__(self):
        self.adb_path = self._find_or_download_adb()
        self.device = None
        self.alpine_installed = self._check_alpine_installed()
        
    def _check_alpine_installed(self) -> bool:
        """Check if Alpine minirootfs exists"""
        return Path(ALPINE_FILENAME).exists()
        
    def _find_or_download_adb(self) -> str:
        """Find ADB or download it"""
        system = platform.system()
        
        try:
            result = subprocess.run(['adb', 'version'], capture_output=True, text=True)
            if result.returncode == 0:
                return 'adb'
        except FileNotFoundError:
            pass
        
        adb_name = 'adb.exe' if system == 'Windows' else 'adb'
        local_adb = Path(f'./platform-tools/{adb_name}')
        if local_adb.exists():
            return str(local_adb)
        
        self._download_adb(system)
        return str(local_adb)
    
    def _download_adb(self, system: str) -> None:
        """Download ADB for the current system"""
        console.print("[*] Downloading ADB...", style="yellow")
        
        urls = {
            'Windows': 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip',
            'Darwin': 'https://dl.google.com/android/repository/platform-tools-latest-darwin.zip',
            'Linux': 'https://dl.google.com/android/repository/platform-tools-latest-linux.zip'
        }
        
        try:
            url = urls.get(system, urls['Linux'])
            urllib.request.urlretrieve(url, 'platform-tools.zip')
            
            with zipfile.ZipFile('platform-tools.zip', 'r') as zip_ref:
                zip_ref.extractall()
            
            os.remove('platform-tools.zip')
            console.print("[+] ADB downloaded", style="green")
        except Exception as e:
            console.print(f"[-] Failed: {e}", style="red")
            sys.exit(1)
    
    def find_devices(self) -> List[Tuple[str, str]]:
        """Find connected ADB devices"""
        try:
            result = subprocess.run(
                [self.adb_path, 'devices', '-l'],
                capture_output=True,
                text=True
            )
            lines = result.stdout.strip().split('\n')[1:]
            
            usb_devices = []
            wifi_devices = []
            
            for line in lines:
                if not line.strip() or 'device' not in line:
                    continue
                
                parts = line.split()
                device_id = parts[0]
                
                if ':5555' in device_id:
                    wifi_devices.append((device_id, 'WiFi'))
                else:
                    usb_devices.append((device_id, 'USB'))
            
            return usb_devices + wifi_devices
        except Exception as e:
            console.print(f"[-] Error: {e}", style="red")
            return []
    
    def select_device(self) -> bool:
        """Find and select a device"""
        console.print(Panel("RAILGUN - Android Device Manager", style="cyan"))
        
        devices = self.find_devices()
        
        if not devices:
            console.print("[-] No devices found", style="red")
            return False
        
        if len(devices) == 1:
            self.device = devices[0][0]
            console.print(f"[+] Device: {self.device} ({devices[0][1]})", style="green")
            return True
        
        choices = [f"{d[0]} ({d[1]})" for d in devices]
        selected = questionary.select(
            "Select device:",
            choices=choices,
            pointer="➜"
        ).ask()
        
        if selected:
            self.device = selected.split()[0]
            console.print(f"[+] Selected: {self.device}", style="green")
            return True
        
        return False
    
    def get_apps(self, app_type: str = "all") -> List[App]:
        """Get list of applications"""
        if not self.device:
            return []
        
        try:
            if app_type == "system":
                cmd = [self.adb_path, '-s', self.device, 'shell', 'pm', 'list', 'packages', '-s']
            elif app_type == "user":
                cmd = [self.adb_path, '-s', self.device, 'shell', 'pm', 'list', 'packages', '-3']
            else:
                cmd = [self.adb_path, '-s', self.device, 'shell', 'pm', 'list', 'packages']
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            packages = [line.replace('package:', '').strip() for line in result.stdout.split('\n') if line.strip()]
            
            apps = []
            with Progress(transient=True) as progress:
                task = progress.add_task("[cyan]Loading apps...", total=len(packages))
                
                for package in packages:
                    try:
                        dump = subprocess.run(
                            [self.adb_path, '-s', self.device, 'shell', 'pm', 'dump', package],
                            capture_output=True,
                            text=True,
                            timeout=1
                        )
                        
                        name = package
                        for line in dump.stdout.split('\n'):
                            if 'label=' in line:
                                name = line.split('label=')[1].strip()
                                break
                        
                        app_type_str = "System" if app_type == "system" else "User" if app_type == "user" else "Unknown"
                        apps.append(App(name, package, app_type_str))
                    except:
                        pass
                    
                    progress.update(task, advance=1)
            
            return apps
        except Exception as e:
            console.print(f"[-] Error: {e}", style="red")
            return []
    
    def uninstall_app(self, package: str) -> bool:
        """Uninstall application"""
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'pm', 'uninstall', '--user', '0', package],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            console.print(f"[-] Error: {e}", style="red")
            return False
    
    def install_app(self, apk_path: str) -> bool:
        """Install application from APK"""
        apk_path = apk_path.strip()
        if not apk_path or not os.path.exists(apk_path):
            console.print(f"[-] File not found: {apk_path}", style="red")
            return False
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'install', apk_path],
                capture_output=True,
                text=True
            )
            return "Success" in result.stdout
        except Exception as e:
            console.print(f"[-] Error: {e}", style="red")
            return False
    def _download_alpine(self) -> bool:
        """Download Alpine minirootfs"""
        console.print("\n[*] Downloading Alpine minirootfs 3.23.3 aarch64...", style="yellow")
        
        try:
            with Progress() as progress:
                task = progress.add_task("[cyan]Downloading...", total=100)
                
                def download_progress(block_num, block_size, total_size):
                    if total_size > 0:
                        downloaded = min(block_num * block_size, total_size)
                        progress.update(task, completed=int((downloaded / total_size) * 100))
                
                urllib.request.urlretrieve(ALPINE_URL, ALPINE_FILENAME, reporthook=download_progress)
            
            console.print("[+] Alpine downloaded", style="green")
            self.alpine_installed = True
            return True
        except Exception as e:
            console.print(f"[-] Download failed: {e}", style="red")
            return False
    
    def _check_root_access(self) -> bool:
        """Check if device has root access"""
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'su', '-c', 'id'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and 'uid=0' in result.stdout
        except:
            return False
    
    def _check_alpine_on_device(self) -> bool:
        """Check if Alpine is already installed on device"""
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'su', '-c', f'test -d {CHROOT_PATH}/bin && test -f {CHROOT_PATH}/etc/alpine-release'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def _get_device_info(self) -> dict:
        """Get device information"""
        info = {}
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'getprop ro.product.model'],
                capture_output=True,
                text=True,
                timeout=5
            )
            info['model'] = result.stdout.strip() or "Unknown"
        except:
            info['model'] = "Unknown"
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'getprop ro.serialno'],
                capture_output=True,
                text=True,
                timeout=5
            )
            info['imei'] = result.stdout.strip() or "Unknown"
        except:
            info['imei'] = "Unknown"
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'getprop ro.build.version.release'],
                capture_output=True,
                text=True,
                timeout=5
            )
            info['android'] = result.stdout.strip() or "Unknown"
        except:
            info['android'] = "Unknown"
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'date \'+%I:%M %p\''],
                capture_output=True,
                text=True,
                timeout=5
            )
            time_str = result.stdout.strip()
            if time_str and time_str != "Unknown":
                info['time'] = time_str
            else:
                result = subprocess.run(
                    [self.adb_path, '-s', self.device, 'shell', 'date \'+%H:%M\''],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                info['time'] = result.stdout.strip() or "Unknown"
        except:
            info['time'] = "Unknown"
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'pm list packages -3 | wc -l'],
                capture_output=True,
                text=True,
                timeout=10
            )
            info['user_apps'] = result.stdout.strip() or "0"
        except:
            info['user_apps'] = "0"
        
        info['alpine'] = "✓" if self._check_alpine_on_device() else "✗"
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'dumpsys battery | grep -E "level|status"'],
                capture_output=True,
                text=True,
                timeout=5
            )
            battery_info = result.stdout.strip()
            level = "Unknown"
            status = "Unknown"
            
            for line in battery_info.split('\n'):
                if 'level:' in line:
                    level = line.split(':')[1].strip()
                elif 'status:' in line:
                    status_num = line.split(':')[1].strip()
                    status = "Charging" if status_num == "2" else "Discharging"
            
            info['battery'] = f"{level}% ({status})"
        except:
            info['battery'] = "Unknown"
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'ip addr show | grep "inet " | grep -v 127.0.0.1 | awk \'{print $2}\' | cut -d/ -f1'],
                capture_output=True,
                text=True,
                timeout=5
            )
            ip_list = result.stdout.strip().split('\n')
            info['ip'] = ip_list[0] if ip_list and ip_list[0] else "Not connected"
        except:
            info['ip'] = "Unknown"
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'getprop ro.build.fingerprint'],
                capture_output=True,
                text=True,
                timeout=5
            )
            info['build'] = result.stdout.strip() or "Unknown"
        except:
            info['build'] = "Unknown"
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'getprop ro.product.cpu.abi'],
                capture_output=True,
                text=True,
                timeout=5
            )
            info['cpu_abi'] = result.stdout.strip() or "Unknown"
        except:
            info['cpu_abi'] = "Unknown"
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'getprop ro.build.fingerprint'],
                capture_output=True,
                text=True,
                timeout=5
            )
            info['build'] = result.stdout.strip() or "Unknown"
        except:
            info['build'] = "Unknown"
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'getprop ro.product.manufacturer'],
                capture_output=True,
                text=True,
                timeout=5
            )
            info['manufacturer'] = result.stdout.strip() or "Unknown"
        except:
            info['manufacturer'] = "Unknown"
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'getprop ro.build.version.sdk'],
                capture_output=True,
                text=True,
                timeout=5
            )
            info['sdk'] = result.stdout.strip() or "Unknown"
        except:
            info['sdk'] = "Unknown"
        
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', 'getprop ro.build.version.security_patch'],
                capture_output=True,
                text=True,
                timeout=5
            )
            info['security_patch'] = result.stdout.strip() or "Unknown"
        except:
            info['security_patch'] = "Unknown"
        
        return info
    
    def show_device_info(self) -> None:
        """Show device information with expandable items"""
        devices = self.find_devices()
        
        if not devices:
            console.print("\n[-] No devices currently at ADB", style="red")
            input("Press Enter to continue...")
            return
        
        device_index = 0
        expanded = False
        info_cache = {}
        
        while True:
            console.clear()
            console.print(Panel("DEVICE INFO", style="bold cyan"))
            
            current_device = devices[device_index]
            self.device = current_device[0]
            device_type = current_device[1]
            
            if self.device not in info_cache:
                info_cache[self.device] = self._get_device_info()
            
            info = info_cache[self.device]
            
            marker = "▼" if expanded else "▶"
            console.print(f"\n{marker} {info['model']} - {device_type}\n", style="cyan")
            
            if expanded:
                console.print(f"  IMEI: {info['imei']}")
                console.print(f"  Manufacturer: {info['manufacturer']}")
                console.print(f"  Android: {info['android']}")
                console.print(f"  SDK: {info['sdk']}")
                console.print(f"  Security Patch: {info['security_patch']}")
                console.print(f"  Time: {info['time']}")
                console.print(f"  IP: {info['ip']}")
                console.print(f"  CPU ABI: {info['cpu_abi']}")
                console.print(f"  Build: {info['build']}")
                console.print(f"  User Apps: {info['user_apps']}")
                console.print(f"  Alpine: {info['alpine']}")
                console.print(f"  Battery: {info['battery']}")
            
            console.print(f"\nDevice {device_index + 1}/{len(devices)}")
            console.print("Controls: ↑↓ Navigate | Enter Expand/Collapse | Q Quit")
            
            key = input().lower()
            
            if key == 'q':
                break
            elif key == '\x1b[A' or key == 'w':
                if device_index > 0:
                    device_index -= 1
                    expanded = False
            elif key == '\x1b[B' or key == 's':
                if device_index < len(devices) - 1:
                    device_index += 1
                    expanded = False
            elif key == '' or key == 'e':
                expanded = not expanded
    
    def _setup_alpine_on_device(self) -> bool:
        """Setup Alpine on selected device"""
        console.print("\n[*] Setting up Alpine on device...", style="yellow")
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Installing Alpine...", total=6)
            
            try:
                subprocess.run(
                    [self.adb_path, '-s', self.device, 'shell', f'mkdir -p {CHROOT_PATH}'],
                    capture_output=True,
                    timeout=10
                )
                progress.update(task, advance=1)
            except Exception as e:
                console.print(f"[-] Failed to create directory: {e}", style="red")
                return False
            
            try:
                subprocess.run(
                    [self.adb_path, '-s', self.device, 'push', ALPINE_FILENAME, f'{CHROOT_PATH}/alpine.tar.gz'],
                    capture_output=True,
                    timeout=60
                )
                progress.update(task, advance=1)
            except Exception as e:
                console.print(f"[-] Failed to push archive: {e}", style="red")
                return False
            
            try:
                subprocess.run(
                    [self.adb_path, '-s', self.device, 'shell', f'cd {CHROOT_PATH} && tar -xzf alpine.tar.gz && rm alpine.tar.gz'],
                    capture_output=True,
                    timeout=60
                )
                progress.update(task, advance=1)
            except Exception as e:
                console.print(f"[-] Failed to extract: {e}", style="red")
                return False
            
            mounts = [('proc', '/proc'), ('sysfs', '/sys'), ('devtmpfs', '/dev'), ('devpts', '/dev/pts')]
            for fstype, target in mounts:
                try:
                    subprocess.run(
                        [self.adb_path, '-s', self.device, 'shell', f'su -c "mount -t {fstype} {fstype} {CHROOT_PATH}{target} 2>/dev/null"'],
                        capture_output=True,
                        timeout=10
                    )
                except:
                    pass
            progress.update(task, advance=1)
            
            try:
                apk_cmd = f'su -c "cd {CHROOT_PATH} && wget https://dl-cdn.alpinelinux.org/alpine/latest-stable/main/aarch64/apk-tools-static-latest.apk && tar -xzf apk-tools-static-latest.apk && ./sbin/apk.static --root . --initdb add apk-tools && rm apk-tools-static-latest.apk"'
                subprocess.run(
                    [self.adb_path, '-s', self.device, 'shell', apk_cmd],
                    capture_output=True,
                    timeout=120
                )
                progress.update(task, advance=1)
            except Exception as e:
                console.print(f"[-] Failed to install apk-tools: {e}", style="red")
                return False
            
            progress.update(task, advance=1)
        
        console.print("[+] Alpine installed successfully!", style="green")
        Path(SETUP_FLAG).touch()
        return True
    
    def show_setup_alpine(self) -> bool:
        """Show Alpine setup menu"""
        console.clear()
        console.print(Panel("SETUP ALPINE ON YOUR DEVICE", style="bold cyan"))
        
        devices = self.find_devices()
        if not devices:
            console.print("[-] No devices found", style="red")
            input("\nPress Enter...")
            return False
        
        if len(devices) == 1:
            self.device = devices[0][0]
            device_name = f"{devices[0][0]} - {devices[0][1]}"
        else:
            choices = [f"{d[0]} - {d[1]}" for d in devices]
            selected = questionary.select(
                "Select device:",
                choices=choices,
                pointer="➜"
            ).ask()
            
            if not selected:
                return False
            
            self.device = selected.split()[0]
            device_name = selected
        
        console.print(f"[+] Selected: {device_name}", style="green")
        
        if self._check_alpine_on_device():
            console.print("\n[+] Alpine is already installed on this device!", style="green")
            use_existing = questionary.confirm("Use existing Alpine installation?").ask()
            if use_existing:
                Path(SETUP_FLAG).touch()
                return True
            else:
                console.print("[-] Setup cancelled", style="red")
                return False
        
        confirm = questionary.select(
            "Do you want to install Alpine rootfs on your device?\n(Safe, running in chroot container)",
            choices=["Yes", "No"],
            pointer="➜"
        ).ask()
        
        if confirm != "Yes":
            return False
        
        console.print("\n[*] Checking root access...", style="yellow")
        if not self._check_root_access():
            console.print("\n[-] Root access denied!", style="red")
            console.print("\nTo enable root access:", style="yellow")
            console.print("1. Make sure you have rooted device")
            console.print("2. Go to Magisk and allow root to com.android.shell in Superuser page")
            console.print("3. When you enabled, answer below:\n")
            
            retry = questionary.select(
                "Try again?",
                choices=["Yes, i enabled", "No, return to main menu"],
                pointer="➜"
            ).ask()
            
            if retry != "Yes, i enabled":
                return False
            
            if not self._check_root_access():
                console.print("[-] Still no root access", style="red")
                input("\nPress Enter...")
                return False
        
        if not self._setup_alpine_on_device():
            input("\nPress Enter...")
            return False
        
        next_action = questionary.select(
            "Installed. What next?",
            choices=["Back to main menu", "Go to ADB Shell", "Exit railgun"],
            pointer="➜"
        ).ask()
        
        if next_action == "Go to ADB Shell":
            self.show_shell()
        elif next_action == "Exit railgun":
            sys.exit(0)
        
        return True
    
    def show_app_manager(self) -> None:
        """Show app manager UI"""
        while True:
            choice = questionary.select(
                "App Manager",
                choices=[
                    "User Apps",
                    "System Apps",
                    "All Apps",
                    "Install APK",
                    "Railgun Repository",
                    "Back"
                ],
                pointer="➜"
            ).ask()
            
            if choice == "Back":
                break
            elif choice == "Install APK":
                apk_path = questionary.text("APK path:").ask()
                if apk_path and self.install_app(apk_path):
                    console.print("[+] Installed successfully", style="green")
                    input("\nPress Enter...")
                elif apk_path:
                    console.print("[-] Installation failed", style="red")
                    input("\nPress Enter...")
            elif choice == "Railgun Repository":
                self._show_railgun_repository()
            else:
                app_type = {"User Apps": "user", "System Apps": "system", "All Apps": "all"}[choice]
                self._show_apps_list(app_type)
    
    def _show_railgun_repository(self) -> None:
        """Show Railgun Repository apps"""
        console.print("\n[*] Fetching Railgun Repository...", style="yellow")
        
        try:
            result = subprocess.run(
                ['curl', '-s', f'{RAILGUN_REPO_URL}/'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                console.print("[-] Failed to fetch repository", style="red")
                input("\nPress Enter...")
                return
            
            import re
            apks = re.findall(r'href=["\']([^"\']*\.apk)["\']', result.stdout)
            
            if not apks:
                console.print("[-] No apps found in repository", style="red")
                input("\nPress Enter...")
                return
            
            choice = questionary.select(
                "Railgun Repository",
                choices=apks + ["Back"],
                pointer="➜"
            ).ask()
            
            if choice == "Back" or not choice:
                return
            
            console.print(f"\n[*] Downloading {choice}...", style="yellow")
            download_url = f"{RAILGUN_REPO_URL}/{choice}"
            
            result = subprocess.run(
                ['curl', '-L', '-o', choice, download_url],
                capture_output=True,
                timeout=60
            )
            
            if result.returncode == 0 and os.path.exists(choice):
                console.print(f"[*] Installing {choice}...", style="yellow")
                if self.install_app(choice):
                    console.print("[+] Installed successfully", style="green")
                    os.remove(choice)
                else:
                    console.print("[-] Installation failed", style="red")
                input("\nPress Enter...")
            else:
                console.print("[-] Download failed", style="red")
                input("\nPress Enter...")
        except Exception as e:
            console.print(f"[-] Error: {e}", style="red")
            input("\nPress Enter...")
    
    def _show_apps_list(self, app_type: str) -> None:
        """Show apps list and allow management"""
        console.print(f"\n[*] Loading {app_type} apps...", style="yellow")
        
        apps = self.get_apps(app_type)
        
        if not apps:
            console.print("[-] No apps found", style="red")
            input("\nPress Enter...")
            return
        
        while True:
            console.clear()
            console.print(Panel(f"{app_type.upper()} APPS ({len(apps)})", style="cyan"))
            
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("ID", style="dim")
            table.add_column("Name")
            table.add_column("Package")
            
            for i, app in enumerate(apps[:20], 1):
                table.add_row(str(i), app.name[:30], app.package[:40])
            
            console.print(table)
            
            if len(apps) > 20:
                console.print(f"\n[*] Showing 20 of {len(apps)} apps")
            
            choices = [f"{i}" for i in range(1, min(21, len(apps) + 1))] + ["Back"]
            
            choice = questionary.select(
                "Select app to uninstall (or Back):",
                choices=choices,
                pointer="➜"
            ).ask()
            
            if choice == "Back":
                break
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(apps):
                    app = apps[idx]
                    if questionary.confirm(f"Uninstall {app.name}?").ask():
                        console.print("[*] Uninstalling...", style="yellow")
                        if self.uninstall_app(app.package):
                            console.print("[+] Uninstalled", style="green")
                            apps.pop(idx)
                        else:
                            console.print("[-] Failed", style="red")
                        input("\nPress Enter...")
            except:
                pass
    
    def show_shell(self) -> None:
        """Show shell option"""
        if not self.device:
            console.print("[-] No device selected", style="red")
            return
        
        console.print(f"\n[+] Starting shell on {self.device}", style="green")
        console.print("[*] Type 'exit' to quit\n", style="yellow")
        
        try:
            subprocess.run([self.adb_path, '-s', self.device, 'shell'])
        except KeyboardInterrupt:
            console.print("\n[*] Shell closed", style="yellow")
        except Exception as e:
            console.print(f"[-] Error: {e}", style="red")
    
    def show_linux_shell(self) -> None:
        """Show Linux chroot shell - interactive"""
        if not self.device:
            console.print("[-] No device selected", style="red")
            return
        
        first_run = Path(SETUP_FLAG).exists()
        
        if first_run:
            console.clear()
            console.print(Panel("WELCOME TO ALPINE LINUX", style="bold cyan"))
            console.print("\nHello to alpine linux railgun container.", style="cyan")
            
            install_apk = questionary.select(
                "Do you want install APK (Alpine packet manager)?\nIts very recommended. (Fast)",
                choices=["Yes (VERY RECOMMENDED)", "No, let me use rootfs. I know what im doing!"],
                pointer="➜"
            ).ask()
            
            self._setup_dns()
            
            if install_apk == "Yes (VERY RECOMMENDED)":
                console.print("\n[*] Installing APK...", style="yellow")
                if not self._install_apk_in_chroot():
                    console.print("[-] APK setup failed, retrying...", style="yellow")
                    self._install_apk_in_chroot()
                else:
                    console.print("[+] APK installed successfully", style="green")
            
            setup_dirs = questionary.select(
                "Last question. Do you want create recommended directories and install recommended packages to start using Alpine?",
                choices=["Yes", "No"],
                pointer="➜"
            ).ask()
            
            if setup_dirs == "Yes":
                console.print("\n[*] Setting up directories...", style="yellow")
                self._setup_alpine_directories()
                console.print("[+] Setup complete", style="green")
            
            Path(SETUP_FLAG).unlink(missing_ok=True)
            input("\nPress Enter to start shell...")
        
        console.print(f"\n[+] Linux Shell on {self.device}", style="green")
        console.print("[*] Type 'exit' to quit\n", style="yellow")
        
        try:
            subprocess.call([
                self.adb_path, '-s', self.device, 'shell',
                f'su -c "export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin; export PS1=\'railgun> \'; chroot {CHROOT_PATH} /bin/bash"'
            ])
        except KeyboardInterrupt:
            console.print("\n[*] Shell closed", style="yellow")
        except Exception as e:
            console.print(f"[-] Error: {e}", style="red")
    
    def _setup_dns(self) -> None:
        """Setup DNS in Alpine"""
        dns_cmd = f'su -c "echo nameserver {DNS_SERVER} > {CHROOT_PATH}/etc/resolv.conf"'
        subprocess.run(
            [self.adb_path, '-s', self.device, 'shell', dns_cmd],
            capture_output=True,
            timeout=10
        )
    
    def _setup_network_config(self) -> None:
        """Setup network configuration and repositories"""
        console.print("\n[*] Configuring network and repositories...", style="yellow")
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Setting up network...", total=5)
            
            dns_setup = f'su -c "chroot {CHROOT_PATH} /bin/sh -c \'echo nameserver {DNS_SERVER} > /etc/resolv.conf && echo nameserver 1.1.1.1 >> /etc/resolv.conf\'"'
            subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', dns_setup],
                capture_output=True,
                timeout=30
            )
            progress.update(task, advance=1)
            
            ca_certs = f'su -c "chroot {CHROOT_PATH} /bin/sh -c \'apk add --no-cache ca-certificates curl wget\'"'
            subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', ca_certs],
                capture_output=True,
                timeout=60
            )
            progress.update(task, advance=1)
            
            repos_content = "\n".join([f"{repo}" for repo in ALPINE_REPOS])
            repos_cmd = f'su -c "chroot {CHROOT_PATH} /bin/sh -c \'echo \\\"{repos_content}\\\" > /etc/apk/repositories\'"'
            subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', repos_cmd],
                capture_output=True,
                timeout=30
            )
            progress.update(task, advance=1)
            
            apk_update = f'su -c "chroot {CHROOT_PATH} /bin/sh -c \'apk update\'"'
            subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', apk_update],
                capture_output=True,
                timeout=120
            )
            progress.update(task, advance=1)
            
            network_tools = f'su -c "chroot {CHROOT_PATH} /bin/sh -c \'apk add --no-cache net-tools iproute2 iputils\'"'
            subprocess.run(
                [self.adb_path, '-s', self.device, 'shell', network_tools],
                capture_output=True,
                timeout=60
            )
            progress.update(task, advance=1)
        
        console.print("[+] Network configured", style="green")
    
    def _install_apk_in_chroot(self) -> bool:
        """Install APK tools in chroot"""
        apk_setup = f'su -c "chroot {CHROOT_PATH} /bin/sh -c \'echo nameserver {DNS_SERVER} > /etc/resolv.conf && apk update && apk add --no-cache ca-certificates\'"'
        result = subprocess.run(
            [self.adb_path, '-s', self.device, 'shell', apk_setup],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            self._setup_network_config()
        
        return result.returncode == 0
    
    def _setup_alpine_directories(self) -> None:
        """Setup recommended directories in Alpine"""
        setup_cmd = f'su -c "chroot {CHROOT_PATH} /bin/sh -c \'mkdir -p /tmp /var/tmp /var/cache /var/log /root && chmod 1777 /tmp /var/tmp\'"'
        subprocess.run(
            [self.adb_path, '-s', self.device, 'shell', setup_cmd],
            capture_output=True,
            timeout=60
        )
    
    def main_menu(self) -> None:
        """Main menu"""
        while True:
            console.clear()
            console.print(Panel("RAILGUN - Android Toolbox", style="bold cyan"))
            
            choices = ["Device Info", "App Manager", "Shell", "Linux Shell", "Exit"]
            if not self.alpine_installed:
                choices.insert(1, "Setup Alpine")
            
            choice = questionary.select(
                "Select option:",
                choices=choices,
                pointer="➜"
            ).ask()
            
            if choice == "Device Info":
                self.show_device_info()
            elif choice == "Setup Alpine":
                if self.show_setup_alpine():
                    self.alpine_installed = True
            elif choice == "App Manager":
                self.show_app_manager()
            elif choice == "Shell":
                self.show_shell()
            elif choice == "Linux Shell":
                self.show_linux_shell()
            elif choice == "Exit":
                console.print("[*] Goodbye!", style="cyan")
                break
    
    def run(self) -> None:
        """Main entry point"""
        if self.select_device():
            if not self.alpine_installed:
                console.clear()
                console.print(Panel("FIRST TIME SETUP", style="bold cyan"))
                console.print("\n[*] Alpine minirootfs not found", style="yellow")
                
                setup_now = questionary.confirm("Download and setup Alpine now?").ask()
                if setup_now:
                    if not self._download_alpine():
                        console.print("[-] Setup cancelled", style="red")
                        sys.exit(1)
                    self.show_setup_alpine()
                else:
                    console.print("[*] You can setup Alpine later from the menu", style="yellow")
                    input("\nPress Enter...")
            
            self.main_menu()
        else:
            sys.exit(1)

if __name__ == '__main__':
    railgun = Railgun()
    railgun.run()
