# macOS VM on Proxmox (AMD Ryzen)

## Overview

This guide documents the working configuration for running macOS Sequoia on Proxmox with AMD Ryzen processors.

## Requirements

- Proxmox VE 8.x or later
- AMD Ryzen CPU (tested on Ryzen 7 7700X)
- OpenCore bootloader ISO
- macOS installer ISO

## Working VM Configuration

### Create VM

```bash
# Create base VM
qm create 200 --name gitlab-runner-macos-sequoia \
    --ostype other \
    --memory 16384 \
    --cores 4 \
    --cpu Penryn \
    --bios ovmf \
    --machine q35 \
    --net0 virtio,bridge=vmbr0 \
    --scsihw virtio-scsi-pci

# Create EFI disk
qm set 200 --efidisk0 local-lvm:1,efitype=4m,size=1M

# Create main disk as SATA (macOS doesn't see SCSI/VirtIO without drivers)
qm set 200 --sata0 local-lvm:64,discard=on,ssd=1

# Set boot order
qm set 200 --boot order=sata0
```

### macOS-Specific Args (AMD Ryzen)

```bash
qm set 200 --args "-device isa-applesmc,osk=ourhardworkbythesewordsguardedpleasedontsteal\(c\)AppleComputerInc -smbios type=2 -global nec-usb-xhci.msi=off -global ICH9-LPC.disable_s3=1 -cpu Penryn,kvm=on,vendor=GenuineIntel,+invtsc,vmware-cpuid-freq=on,+pcid,+ssse3,+sse4.2,+popcnt,+avx,+aes,+xsave,+xsaveopt,check -drive id=OpenCore,if=none,snapshot=on,format=raw,file=/var/lib/vz/template/iso/OpenCore-v21.iso -device usb-storage,drive=OpenCore -drive id=MacInstaller,if=none,snapshot=on,format=raw,file=/var/lib/vz/template/iso/macOS_Sequoia_15.7.3.iso -device usb-storage,drive=MacInstaller -device usb-kbd -device usb-tablet"
```

### Key Configuration Notes

1. **CPU Type**: Use `Penryn` (NOT `host`) - AMD Ryzen causes kernel panics with host passthrough
2. **Disk Type**: Use `sata0` (NOT `scsi0`) - macOS cannot see VirtIO/SCSI disks without additional drivers
3. **CPU Flags**:
   - `kvm=on` - Enable KVM
   - `vendor=GenuineIntel` - Spoof Intel vendor ID
   - `+invtsc` - Invariant TSC for timing
   - `vmware-cpuid-freq=on` - TSC frequency reporting
   - `+ssse3,+sse4.2,+popcnt,+avx,+aes,+xsave,+xsaveopt` - Required CPU features
4. **Apple SMC**: The OSK (OS Key) is required for macOS to boot
5. **S3 Sleep**: Disabled with `ICH9-LPC.disable_s3=1` to prevent sleep issues

### Final Working Config

```
args: -device isa-applesmc,osk=ourhardworkbythesewordsguardedpleasedontsteal\(c\)AppleComputerInc -smbios type=2 -global nec-usb-xhci.msi=off -global ICH9-LPC.disable_s3=1 -cpu Penryn,kvm=on,vendor=GenuineIntel,+invtsc,vmware-cpuid-freq=on,+pcid,+ssse3,+sse4.2,+popcnt,+avx,+aes,+xsave,+xsaveopt,check -drive id=OpenCore,if=none,snapshot=on,format=raw,file=/var/lib/vz/template/iso/OpenCore-v21.iso -device usb-storage,drive=OpenCore -drive id=MacInstaller,if=none,snapshot=on,format=raw,file=/var/lib/vz/template/iso/macOS_Sequoia_15.7.3.iso -device usb-storage,drive=MacInstaller -device usb-kbd -device usb-tablet
bios: ovmf
boot: order=sata0
cores: 4
cpu: Penryn
efidisk0: local-lvm:vm-200-disk-0,efitype=4m,size=4M
machine: q35
memory: 16384
name: gitlab-runner-macos-sequoia
net0: virtio=BC:24:11:80:A0:0C,bridge=vmbr0
ostype: other
sata0: local-lvm:vm-200-disk-1,discard=on,size=64G,ssd=1
scsihw: virtio-scsi-pci
```

## Installation Process

1. Start VM and open console in Proxmox web UI
2. OpenCore will boot - select "Install macOS Sequoia"
3. Use Disk Utility to format the SATA disk as APFS
4. Run macOS installer
5. After install, boot from internal disk via OpenCore

## Post-Installation

After macOS is installed:

1. Remove the installer ISO from args (keep OpenCore)
2. Install GitLab Runner:
   ```bash
   brew install gitlab-runner
   gitlab-runner install
   gitlab-runner start
   ```

## Troubleshooting

### Kernel Panic at Apple Logo
- Ensure CPU type is `Penryn`, not `host`
- Check all CPU flags are correct

### Disk Not Visible in Disk Utility
- Use SATA disk type, not SCSI
- Format as APFS (not APFS encrypted for VMs)

### Boot Loops
- Verify OpenCore ISO is correct version
- Check EFI disk is properly configured

## Tested Versions

- Proxmox VE 8.x / 9.x
- macOS Sequoia 15.7.3
- OpenCore v21
- AMD Ryzen 7 7700X
