N4.7 – Xây dựng hệ thống giám sát máy chủ, Cloud và trung tâm dữ liệu
N4 – Mạng, IoT và hạ tầng số
Định hướng phù hợp: Observability cho hạ tầng số, theo dõi sức khỏe dịch vụ và minh họa vận hành theo hướng cloud-native.
Bài toán thực tiễn: Nhóm cần xây dựng dashboard thống nhất cho máy chủ/dịch vụ lab, phát hiện ngưỡng bất thường và minh họa cảnh báo. Đề tài tập trung vào prototype trong môi trường kiểm soát, không thay thế NOC/DCIM chính thức.
Mục tiêu cụ thể
Thu thập metric sức khỏe từ máy chủ/container hoặc dịch vụ mô phỏng.
•	Xây dựng dashboard và luật cảnh báo có thể kiểm thử.
Mô phỏng một số kịch bản lỗi và đánh giá thời gian phát hiện.
Phạm vi thực hiện trong 18 tuần
Chọn một môi trường: Linux VM, Docker hoặc Kubernetes lab.
Theo dõi CPU, RAM, disk, network, uptime và tình trạng endpoint.
Dashboard theo host/service, cảnh báo ngưỡng và lịch sử.
Thử kịch bản CPU cao, disk đầy giả lập, service down; ghi nhận cảnh báo.
Công nghệ gợi ý: Prometheus, Grafana, Node Exporter/cAdvisor; Docker Compose; Alertmanager nếu phù hợp.
Dữ liệu/môi trường thử nghiệm: Metric từ VM/container do nhóm quản lý hoặc môi trường lab được cấp phép.
Sản phẩm bàn giao
Sơ đồ kiến trúc giám sát.
Dashboard và cấu hình cảnh báo có version control.
Bộ kịch bản lỗi và kết quả thử nghiệm.
Runbook xử lý cảnh báo và hướng dẫn dựng lại lab.
Tiêu chí nghiệm thu đề xuất
Metric được thu thập và hiển thị theo thời gian.
Ít nhất ba kịch bản cảnh báo được chứng minh bằng demo.
Có hướng dẫn xử lý và phân biệt cảnh báo giả; không dùng credential sản xuất.
Rủi ro và cách giới hạn phạm vi: Không kết nối nền tảng quản trị trung tâm dữ liệu thật nếu chưa có phân quyền và phê duyệt an toàn thông tin.
Nguồn dữ liệu public đề xuất
•	Google Cluster Data — Trace sử dụng tài nguyên cụm máy tính để nghiên cứu phân bổ tải và giám sát. https://github.com/google/cluster-data
•	Numenta Anomaly Benchmark (NAB) — Chuỗi thời gian benchmark, có một số chỉ số liên quan máy chủ/ứng dụng. https://github.com/numenta/NAB
•	Loghub — Log hệ thống để thử nghiệm cảnh báo và điều tra sự kiện. https://github.com/logpai/loghub
Dữ liệu VNPT nếu được cung cấp
Nếu được phê duyệt: metric CPU/RAM/disk/network đã tổng hợp từ VM lab hoặc máy chủ thử nghiệm; không dùng địa chỉ IP, tên hệ thống, log truy cập hay sơ đồ DC nhạy cảm. Dữ liệu giả lập là đủ cho bản demo.
Tài nguyên và môi trường triển khai
2–3 VM Linux hoặc Docker Compose; Prometheus + Node Exporter + Grafana; Python cho dự báo/cảnh báo; 8–16 GB RAM host. Cloud/GPU không bắt buộc.
Kết quả dự kiến khi nghiệm thu
Một prototype/PoC chạy được trong môi trường thử nghiệm; bộ dữ liệu hoặc pipeline có hướng dẫn tái lập; báo cáo đánh giá theo KPI phù hợp với đề tài; mã nguồn và hướng dẫn cài đặt; slide/demo; danh mục hạn chế và đề xuất bước tiếp theo. Chỉ tiêu định lượng cụ thể cần được UTH và mentor VNPT thống nhất sau khi chốt dữ liệu, không đặt ngưỡng tùy ý trước khi đo baseline.

 