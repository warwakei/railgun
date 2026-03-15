# Railgun

Android device manager and toolbox via ADB. Control your Android device with ease.

## Features

- **Device Info** — View detailed device information (IMEI, Android version, IP, battery, etc.)
- **App Manager** — Install, uninstall, and manage applications
- **ADB Shell** — Direct shell access to your device
- **Linux Shell** — Run Alpine Linux in a chroot container on your device
- **Setup Alpine** — Automatic Alpine Linux installation with network configuration
- **Railgun Repository** — Install curated applications from Railgun Repository

## Requirements

- Python 3.7+
- ADB (automatically downloaded if not found)
- Android device with USB debugging enabled
- Root access (for Alpine Linux features)

## Installation

```bash
python railgun.py
```

On first run, Railgun will:
1. Download ADB if needed
2. Detect connected devices
3. Offer to download and setup Alpine Linux

## Usage

### Device Selection
Connect your Android device via USB and enable USB debugging. Railgun will automatically detect it.

### Device Info
View comprehensive device information including:
- IMEI and manufacturer
- Android version and SDK level
- Security patch date
- Current IP address
- CPU architecture
- Battery status
- Alpine installation status

### App Manager
- Browse user and system applications
- Install APK files
- Uninstall applications
- Access Railgun Repository for curated apps

### Linux Shell
Run a full Alpine Linux environment on your device:
```
railgun> apk add curl
railgun> curl https://example.com
```

First-time setup includes:
- DNS configuration (Google 8.8.8.8 + Cloudflare 1.1.1.1)
- APK package manager installation
- Network tools (net-tools, iproute2, iputils)
- Recommended directories and packages

### Alpine Linux Setup
Automatic installation of Alpine Linux 3.23.3 (aarch64) with:
- Root access verification
- Automatic network configuration
- APK package manager
- System directories setup

## Controls

### Device Info Navigation
- `↑↓` — Navigate between devices
- `Enter` — Expand/collapse device details
- `Q` — Return to main menu

### Main Menu
- Arrow keys to navigate
- Enter to select
- ESC to go back

## Requirements for Alpine Linux

- **Rooted device** — Required for chroot and mount operations
- **Magisk or similar** — For root access management
- **Sufficient storage** — ~200MB for Alpine rootfs

## Troubleshooting

### No devices found
- Enable USB debugging on your device
- Check USB cable connection
- Try `adb devices` in terminal

### Alpine installation fails
- Ensure device is rooted
- Grant root access to `com.android.shell` in Magisk
- Check available storage space

### Linux shell not working
- Verify Alpine is installed (Device Info → Alpine: ✓)
- Ensure device remains connected
- Try reconnecting USB

## License

MIT

## Contributing

Contributions welcome! Feel free to submit issues and pull requests.

---

**Railgun** — Making Android device management simple and powerful.
