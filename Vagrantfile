# -*- mode: ruby -*-
# Lab giám sát 3 VM (ADR-0001). Dựng:  vagrant up      Dựng lại sạch:  vagrant destroy -f; vagrant up
#
# Cấu hình đọc theo thứ tự ưu tiên: biến môi trường > .env > .env.example
# (không cần tạo .env nếu chấp nhận giá trị mặc định của lab).

ROOT = File.dirname(__FILE__)

def read_env_file(path)
  return {} unless File.exist?(path)
  File.readlines(path, encoding: "UTF-8").each_with_object({}) do |line, acc|
    line = line.strip
    next if line.empty? || line.start_with?("#")
    key, value = line.split("=", 2)
    next if value.nil?
    acc[key.strip] = value.strip.sub(/\A["'](.*)["']\z/, '\1')
  end
end

CONF = read_env_file(File.join(ROOT, ".env.example"))
         .merge(read_env_file(File.join(ROOT, ".env")))
         .merge(ENV.to_h.select { |k, _| k.start_with?("VM_", "LAB_", "HOST_PORT_", "POSTGRES_", "PORTAL_", "GRAFANA_", "PROM_") })

def conf(key)
  CONF.fetch(key) { abort "Thiếu biến #{key} trong .env/.env.example" }
end

VMS = {
  "monitor" => { ip: conf("VM_MONITOR_IP"), memory: conf("VM_MONITOR_MEMORY"), cpus: conf("VM_MONITOR_CPUS") },
  "web"     => { ip: conf("VM_WEB_IP"),     memory: conf("VM_WEB_MEMORY"),     cpus: conf("VM_WEB_CPUS") },
  "db"      => { ip: conf("VM_DB_IP"),      memory: conf("VM_DB_MEMORY"),      cpus: conf("VM_DB_CPUS") },
}

# Biến truyền vào script provision. Mật khẩu chỉ là giá trị lab trong .env/.env.example.
COMMON_ENV = {
  "VM_MONITOR_IP"    => conf("VM_MONITOR_IP"),
  "VM_WEB_IP"        => conf("VM_WEB_IP"),
  "VM_DB_IP"         => conf("VM_DB_IP"),
  "LAB_DISK_SIZE_MB" => conf("LAB_DISK_SIZE_MB"),
}

ROLE_ENV = {
  "monitor" => {
    "GRAFANA_ADMIN_USER" => conf("GRAFANA_ADMIN_USER"), "GRAFANA_ADMIN_PASSWORD" => conf("GRAFANA_ADMIN_PASSWORD"),
    "GRAFANA_ANONYMOUS_ENABLED" => conf("GRAFANA_ANONYMOUS_ENABLED"), "PROM_RETENTION" => conf("PROM_RETENTION"),
  },
  "web" => {
    "LAB_DB_NAME" => conf("LAB_DB_NAME"), "LAB_DB_USER" => conf("LAB_DB_USER"),
    "LAB_DB_PASSWORD" => conf("LAB_DB_PASSWORD"),
  },
  "db" => {
    "LAB_DB_NAME" => conf("LAB_DB_NAME"), "LAB_DB_USER" => conf("LAB_DB_USER"),
    "LAB_DB_PASSWORD" => conf("LAB_DB_PASSWORD"),
    "POSTGRES_EXPORTER_PASSWORD" => conf("POSTGRES_EXPORTER_PASSWORD"),
  },
}

Vagrant.configure("2") do |config|
  config.vm.box = conf("LAB_BOX")
  config.vm.box_check_update = false
  config.vm.synced_folder ".", "/vagrant"

  config.vm.provider "virtualbox" do |vb|
    vb.linked_clone = true
    vb.customize ["modifyvm", :id, "--audio-driver", "none"]
    vb.customize ["modifyvm", :id, "--groups", "/obslab"]
  end

  VMS.each do |name, spec|
    config.vm.define name, primary: name == "monitor" do |node|
      node.vm.hostname = name
      node.vm.network "private_network", ip: spec[:ip]

      node.vm.provider "virtualbox" do |vb|
        vb.name = "obslab-#{name}"
        vb.memory = spec[:memory].to_i
        vb.cpus = spec[:cpus].to_i
      end

      if name == "monitor"
        { "PORTAL" => 8080, "GRAFANA" => 3000, "PROMETHEUS" => 9090, "ALERTMANAGER" => 9093 }.each do |svc, guest|
          node.vm.network "forwarded_port", guest: guest, host: conf("HOST_PORT_#{svc}").to_i,
                          host_ip: "127.0.0.1", id: svc.downcase
        end
      end

      node.vm.provision "common", type: "shell", path: "provision/common.sh", env: COMMON_ENV
      node.vm.provision "node_exporter", type: "shell", path: "provision/node_exporter.sh", env: COMMON_ENV
      node.vm.provision name, type: "shell", path: "provision/#{name}.sh", env: COMMON_ENV.merge(ROLE_ENV[name])
    end
  end
end
