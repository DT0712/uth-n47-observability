# Hướng dẫn dựng lab và đo baseline trên máy của bạn

Dành cho thành viên nhóm. Mục tiêu: dựng lab 3 VM, đo baseline 24 giờ, rồi gửi kết quả để nhóm so sánh giữa các máy
trước khi chốt ngưỡng. Mọi lệnh chạy trong **PowerShell** tại thư mục repo (WSL cũng được, đổi `\` thành `/`).

## 1. Chuẩn bị

| Cần | Ghi chú |
|---|---|
| Windows 10/11, RAM ≥ 12 GB, đĩa trống ≥ 30 GB | 3 VM dùng 4,5 GB RAM (monitor 2 GB, web 1 GB, db 1,5 GB) |
| VirtualBox 7.x, Vagrant 2.4.x, Python ≥ 3.10, Git | Máy mẫu: VirtualBox 7.2.22, Vagrant 2.4.9, Python 3.13 |
| Bật ảo hóa (VT-x/AMD-V) trong BIOS | Nếu Hyper-V/WSL2 bật, VirtualBox vẫn chạy được nhưng chậm hơn |

Python chỉ dùng thư viện chuẩn, không cần `pip install`.

```powershell
git clone https://github.com/DT0712/uth-n47-observability.git
cd uth-n47-observability
```

Không cần tạo `.env`: Vagrantfile đọc `.env.example`. Chỉ tạo `.env` (`Copy-Item .env.example .env`) khi phải đổi giá trị,
vd. cổng bị trùng. **Không** giảm RAM của VM: kết quả sẽ không so được với máy khác. Không ghi mật khẩu thật vào file nào.

## 2. Dựng lab

```powershell
vagrant up                                          # lần đầu ~15–20 phút (tải box), các lần sau ~5 phút
python tools/check_lab.py --wait 180 --test-alert   # phải kết thúc bằng "TẤT CẢ OK ✓"
```

Kiểm tra độ trễ đánh giá luật của Prometheus ([SC-04](xu-ly-su-co.md#sc-04-prometheus-đánh-giá-luật-trễ-sau-khi-đồng-hồ-nhảy)).
Bắt buộc sau **mỗi** lần `vagrant up`, vì chrony chỉnh giờ VM lúc khởi động:

```powershell
python -c "import sys; sys.path.insert(0, 'tools'); from lib.common import rule_eval_lag; print(rule_eval_lag())"
# Kết quả > 1 (giây) thì khởi động lại Prometheus rồi kiểm tra lại:
vagrant ssh monitor -c "obslab-compose restart prometheus"
```

Gặp lỗi khác: tra [xu-ly-su-co.md](xu-ly-su-co.md).

## 3. Chuẩn bị máy cho 24 giờ

- Cắm sạc, **không gập nắp**: gập nắp làm máy ngủ dù đã tắt chế độ ngủ.
- Tắt ngủ khi cắm sạc: Settings → System → Power → *When plugged in, put my device to sleep after* = **Never**.
- Tạm dừng Windows Update (Settings → Windows Update → *Pause updates*) để máy không tự khởi động lại.
- Đóng ứng dụng nặng (game, máy ảo khác, nhiều tab trình duyệt). Nên có ≥ 2 GB RAM trống trong suốt lúc đo.
- Trong 24 giờ: **không** chạy `tools/fault.py`, không `vagrant halt/reload`, không tắt máy.

## 4. Đo

Mở một cửa sổ PowerShell riêng và để nó chạy (đóng cửa sổ là dừng đo):

```powershell
python tools/baseline.py --minutes 1440 --wait --label baseline-24h-<tên-bạn>
```

Lệnh tự từ chối chạy nếu đang có lỗi giả lập hoặc Prometheus đánh giá luật trễ quá 1 giây. Mỗi 10 phút nó in một dòng sức
khỏe lab và giữ Windows không ngủ do không dùng máy. Xong sẽ tự thống kê.

Xem tiến độ và giờ dự kiến xong (ở cửa sổ khác, lúc nào cũng được):

```powershell
python tools/baseline.py --status
```

Nếu `--status` báo `TIẾN TRÌNH ĐÃ DỪNG` (lỡ đóng cửa sổ...) thì dữ liệu vẫn nằm trong Prometheus. Thống kê phần đã đo:

```powershell
python tools/baseline.py --from-state
```

Lần đo chỉ dùng được khi đủ 24 giờ và mục *Kết luận* trong `baseline.md` ghi "dữ liệu sạch". Nếu máy ngủ, khởi động lại
hoặc mất dữ liệu quá 60 giây, hãy đo lại từ đầu.

## 5. Gửi kết quả

Kết quả nằm ở `results\baseline\<thời điểm>-baseline-24h-<tên-bạn>\`: `baseline.md`, `baseline.csv`, `meta.json`.
Thư mục `results/` không vào git, nên chép sang thư mục kết quả của nhóm:

```powershell
$src = (Get-ChildItem results\baseline -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
$dst = "docs\05-thu-nghiem\baseline\<tên-bạn>-$(Get-Date -Format yyyyMMdd)"
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item "$src\baseline.md", "$src\baseline.csv", "$src\meta.json" $dst
Copy-Item data\baseline\health.jsonl $dst
```

Thêm file `$dst\may.md` ghi cấu hình máy: CPU, RAM, phiên bản Windows/VirtualBox/Vagrant, và việc bất thường trong lúc đo nếu
có (máy chậm, mất điện...).

Gửi qua Git, trên nhánh riêng, **không** đẩy thẳng lên `main`:

```powershell
git checkout -b baseline-<tên-bạn>
git add docs/05-thu-nghiem/baseline/
git commit -m "Baseline 24 giờ trên máy <tên-bạn>"
git push -u origin baseline-<tên-bạn>
```

Sau đó mở pull request trên GitHub. Chưa có quyền push thì nén thư mục `$dst` thành zip và gửi vào nhóm chat.

**Không sửa `thresholds.yml`.** Ngưỡng v1 đã chốt theo máy mẫu ([baseline.md](../05-thu-nghiem/baseline.md)); nhóm xem lại
(v2) sau khi có kết quả của các máy ([ADR-0004](../02-thiet-ke/adr/0004-nguong-canh-bao-dang-recording-rule.md)).

## 6. Sau khi đo

Để lại lab thì cứ để chạy. Tắt máy thì chạy `vagrant halt` trước. **Không** `vagrant destroy`, trừ khi muốn dựng lại từ đầu.
