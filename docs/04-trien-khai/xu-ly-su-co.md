# Xử lý sự cố khi dựng và vận hành lab

Sự cố của **môi trường lab** (Vagrant, VirtualBox, SSH, Windows). Xử lý **cảnh báo** của hệ thống giám sát nằm ở
[runbooks/](../../runbooks/README.md). Lệnh chạy trong PowerShell tại thư mục gốc repo.

| Mã | Triệu chứng |
|---|---|
| [SC-01](#sc-01-vagrant-ssh-hỏi-mật-khẩu) | `vagrant ssh <vm>` hỏi `vagrant@127.0.0.1's password:` |
| [SC-02](#sc-02-vm-ở-trạng-thái-aborted) | `vagrant status` báo VM `aborted` |
| [SC-03](#sc-03-windows-ngủ-làm-đứng-vm) | Biểu đồ có khoảng trống; `fault.py` báo đồng hồ VM lệch hoặc thiếu dữ liệu |

## SC-01: `vagrant ssh` hỏi mật khẩu

**Triệu chứng**
- `vagrant ssh monitor` (hoặc web, db) hỏi `vagrant@127.0.0.1's password:`.
- `vagrant up`/`reload` vẫn báo `SSH auth method: private key` và `Machine booted and ready!`.
- Công cụ gọi `vagrant ssh` (`check_fault_ssh.py`, `reload.py`) treo rồi timeout.
- Cùng lệnh đó chạy trong Git Bash lại được.

**Nguyên nhân**
- `ssh.exe` của Windows từ chối khóa mà người khác đọc/sửa được. Khóa `.vagrant/machines/<vm>/virtualbox/private_key`
  thừa hưởng quyền của thư mục repo, thường có `Authenticated Users: Modify`, nên bị bỏ qua và ssh chuyển sang hỏi mật khẩu.
- Vagrant không siết quyền khóa trên Windows (`lib/vagrant/util/ssh.rb`, bản 2.4.9).
- `vagrant up`/`reload` không gặp lỗi vì dùng thư viện SSH của Ruby, không dùng `ssh.exe`. Git Bash không gặp lỗi vì
  `ssh` của Git không xét quyền NTFS.

**Chẩn đoán**

```powershell
vagrant ssh monitor -c hostname -- -v -o BatchMode=yes -o LogLevel=DEBUG1
```

| Dòng trong kết quả | Ý nghĩa |
|---|---|
| `Server accepts key` rồi `UNPROTECTED PRIVATE KEY FILE` / `bad permissions` | Đúng SC-01: VM bình thường, lỗi quyền file trên Windows |
| `Offering public key` rồi `Permission denied`, không có `Server accepts key` | VM không có khóa này: **không phải** SC-01, xem `authorized_keys` trong VM |
| `Connection refused` / `timed out` | VM chưa chạy hoặc sai cổng: xem `vagrant status`, `vagrant ssh-config <vm>` |

**Khắc phục**
- Vagrantfile tự siết quyền ở mỗi lệnh `vagrant` (từ 2026-11-24). Chạy lại `vagrant ssh <vm>` là đủ, không cần
  `reload`, không cần `destroy`.
- Nếu vẫn lỗi, siết bằng tay:

```powershell
$key = ".vagrant\machines\monitor\virtualbox\private_key"
icacls $key /inheritance:r /grant:r "$env:USERDOMAIN\$env:USERNAME`:F" "*S-1-5-18:F" "*S-1-5-32-544:F"
```

**Xác minh**

```powershell
vagrant ssh monitor -c hostname -- -o BatchMode=yes   # in ra: monitor
python tools\check_fault_ssh.py                       # TẤT CẢ ĐẠT ✓
```

## SC-02: VM ở trạng thái `aborted`

**Nguyên nhân đã gặp (2026-11-24):** Windows tắt máy khi VM còn chạy, VirtualBox bị ngắt giữa chừng. Xác nhận bằng
cách so giờ cuối trong `VBox.log.1` của VM với sự kiện tắt máy:

```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; Id=1074} -MaxEvents 5 | Format-List TimeCreated, Message
```

**Khắc phục**

```powershell
vagrant up
python toolseck_lab.py --wait 180
```

**Phòng tránh:** chạy `vagrant halt` trước khi tắt hoặc khởi động lại Windows. Khoảng thời gian VM tắt là khoảng
trống trong dữ liệu Prometheus; nếu đang đo baseline thì phải đo lại.

## SC-03: Windows ngủ làm đứng VM

**Triệu chứng:** Grafana có khoảng trống trên mọi biểu đồ; `fault.py` báo `đồng hồ ... lệch monitor` hoặc
`thiếu dữ liệu ... trong 2 phút qua`; nhật ký chrony trong VM có `Forward time jump detected`.

**Nguyên nhân đã gặp (2026-11-24):** Windows tự ngủ sau 15 phút không dùng (13:23–13:46), VM đứng theo. Khi thức dậy,
đồng hồ VM lệch tới 1,3 giây và cần khoảng 3 phút để chrony sửa.

**Chẩn đoán**

```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Power'; Id=42,107} -MaxEvents 4
powercfg /q SCHEME_CURRENT SUB_SLEEP STANDBYIDLE      # Current AC/DC ... Index: số giây, dạng hex; 0 = không ngủ
```

**Khắc phục:** chờ khoảng 3–5 phút rồi chạy `python toolseck_lab.py`. Lần đo bị ngủ chen vào phải bỏ và đo lại.

**Phòng tránh:** `fault.py run` tự giữ Windows thức trong lúc chạy. Với việc đo dài (baseline), tắt chế độ ngủ trong
Windows (Settings → System → Power) trước khi bắt đầu.
