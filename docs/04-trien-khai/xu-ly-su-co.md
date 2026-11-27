# Xử lý sự cố khi dựng và vận hành lab

Sự cố của **môi trường lab** (Vagrant, VirtualBox, SSH, Windows) và của portal khi chạy cục bộ. Xử lý **cảnh báo** của hệ thống giám sát nằm ở
[runbooks/](../../runbooks/README.md). Lệnh chạy trong PowerShell tại thư mục gốc repo.

| Mã | Triệu chứng |
|---|---|
| [SC-01](#sc-01-vagrant-ssh-hỏi-mật-khẩu) | `vagrant ssh <vm>` hỏi `vagrant@127.0.0.1's password:` |
| [SC-02](#sc-02-vm-ở-trạng-thái-aborted) | `vagrant status` báo VM `aborted` |
| [SC-03](#sc-03-windows-ngủ-làm-đứng-vm) | Biểu đồ có khoảng trống; `fault.py` báo đồng hồ VM lệch hoặc thiếu dữ liệu |
| [SC-04](#sc-04-prometheus-đánh-giá-luật-trễ-sau-khi-đồng-hồ-nhảy) | `fault.py` báo `Prometheus đánh giá luật trễ`; cảnh báo tới muộn, inhibit không chặn |
| [SC-05](#sc-05-migrate-portal-báo-bảng-_alembic_tmp_-đã-tồn-tại) | `python -m app.db.migrate` báo `table _alembic_tmp_incidents already exists` |

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
python tools\check_lab.py --wait 180
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

**Khắc phục:** chờ khoảng 3–5 phút rồi chạy `python tools\check_lab.py`. Lần đo bị ngủ chen vào phải bỏ và đo lại.

**Phòng tránh:** `fault.py run` tự giữ Windows thức trong lúc chạy. Với việc đo dài (baseline), tắt chế độ ngủ trong
Windows (Settings → System → Power) trước khi bắt đầu.

## SC-04: Prometheus đánh giá luật trễ sau khi đồng hồ nhảy

**Triệu chứng:** `fault.py` báo `Prometheus đánh giá luật trễ ...s`. Lab nhìn vẫn khỏe (`check_lab.py` đạt, chrony đã
đồng bộ) nhưng cảnh báo tới muộn một khoảng không đổi, và cảnh báo hệ quả không bị inhibit.

**Nguyên nhân đã gặp (2026-11-24):** Windows ngủ 13:23–13:46 (SC-03). Prometheus lỡ 94 chu kỳ đánh giá
(`prometheus_rule_group_iterations_missed_total` = 94, đúng 23,5 phút). Sau đó mọi nhóm luật chạy đúng nhịp 15 giây nhưng
trên dữ liệu cũ 10,44 giây, cho tới khi khởi động lại Prometheus. Hệ quả:
- `startsAt` của cảnh báo đã cũ hơn `group_wait` (5 giây) khi tới Alertmanager. Alertmanager gửi ngay, không chờ, nên
  inhibit không kịp chặn.
- Mọi cảnh báo tới muộn thêm khoảng 5,4 giây (10,45 giây thay vì 5 giây sau `startsAt`).

**Khởi động VM cũng gây trễ:** Prometheus chạy trước khi chrony chỉnh giờ. Ngày 2026-11-26, chrony chỉnh 1,346 giây
(`journalctl -u chrony -b`) và độ trễ đo được là 1,351 giây; khởi động lại Prometheus thì còn 0,001 giây. Độ trễ 2 giây
ngày 2026-11-23 (cảnh báo tới 7,0 giây sau `startsAt`) có thể cùng nguyên nhân, nhưng chưa xác minh.

**Chẩn đoán** (bình thường khoảng 0; `None` trong 1–2 phút đầu sau khi khởi động Prometheus)

```powershell
python -c "import sys; sys.path.insert(0, 'tools'); from lib.common import rule_eval_lag; print(rule_eval_lag())"
```

**Khắc phục:** không mất dữ liệu đã lưu.

```powershell
vagrant ssh monitor -c "obslab-compose restart prometheus"
```

**Phòng tránh:** không để Windows ngủ khi lab đang chạy. Sau mỗi lần `vagrant up`, trước khi đo hoặc lấy baseline, kiểm tra
độ trễ bằng lệnh trên và khởi động lại Prometheus nếu quá 1 giây. `fault.py` từ chối đo khi trễ quá 1 giây;
`detection_time.py` loại các lần đo bị trễ.

## SC-05: migrate portal báo bảng `_alembic_tmp_*` đã tồn tại

**Triệu chứng:** `python -m app.db.migrate` trên CSDL SQLite cục bộ (`portal/backend/portal-dev.db`) dừng với
`sqlite3.OperationalError: table _alembic_tmp_incidents already exists`. Chạy lại vẫn lỗi y hệt.

**Nguyên nhân đã gặp (2026-11-26):** SQLite không `ALTER` được khóa ngoại hay ràng buộc CHECK, nên migration dùng
`batch_alter_table`: Alembic tạo bảng tạm `_alembic_tmp_<bảng>`, chép dữ liệu sang, xóa bảng cũ rồi đổi tên bảng tạm.
Lần chạy đầu của migration `7c1e2a9b4d30` (sự cố thử nghiệm) lỗi giữa chừng do tên ràng buộc bị lặp, lỗi này đã sửa.
SQLite không rollback được DDL của Alembic, nên bảng tạm còn sót và `alembic_version` vẫn ở phiên bản cũ. Lần chạy sau
lại tạo bảng tạm cùng tên và vấp lỗi. PostgreSQL (trên VM) rollback được cả DDL nên không gặp lỗi này.

**Chẩn đoán:** dừng backend trước, rồi xem phiên bản, các bảng tạm và cột của bảng chính:

```powershell
cd portal/backend
.venv\Scripts\python -c "import sqlite3; c = sqlite3.connect('portal-dev.db'); print(c.execute('select version_num from alembic_version').fetchall()); print([n for (n,) in c.execute('select name from sqlite_master') if n.startswith('_alembic_tmp')]); print([r[1] for r in c.execute('pragma table_info(incidents)')])"
```

**Khắc phục**, chọn một trong hai cách:

- **Dữ liệu mẫu, không cần giữ** (cách đã dùng 2026-11-26): xóa file rồi nạp lại.

  ```powershell
  Remove-Item portal-dev.db
  .venv\Scripts\python -m app.db.migrate
  .venv\Scripts\python -m app.dev_seed
  ```

- **Cần giữ dữ liệu:** sao lưu file trước. Nếu bảng chính chưa có cột mới (với `7c1e2a9b4d30`: `incidents` chưa có
  `fault_run_id`), bảng cũ vẫn nguyên vẹn và chỉ cần xóa bảng tạm rồi chạy lại migrate. Nếu bảng chính **đã** có cột mới,
  migration đã đi quá bước đó: đừng xóa gì, hãy dùng cách thứ nhất hoặc khôi phục bản sao lưu.

  ```powershell
  Copy-Item portal-dev.db portal-dev.db.bak
  .venv\Scripts\python -c "import sqlite3; c = sqlite3.connect('portal-dev.db'); c.execute('drop table _alembic_tmp_incidents'); c.commit()"
  .venv\Scripts\python -m app.db.migrate
  ```

**Phòng tránh:** viết migration mới thì chạy thử `upgrade`/`downgrade` trên một bản sao CSDL trước (test của backend đã
chạy migration trên SQLite trống). Tên ràng buộc trong `batch_alter_table` phải bọc bằng `batch_op.f(...)` vì đã có quy
ước đặt tên, không thì tên bị lặp (`ck_incident_events_ck_incident_events_type`).
