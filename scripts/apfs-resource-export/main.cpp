// Local read-only adapter to GPL-2.0-or-later apfs-fuse (Simon Gander).
// No target code execution, device nodes, or upstream-source modifications.
#include <ApfsLib/ApfsContainer.h>
#include <ApfsLib/ApfsVolume.h>
#include <ApfsLib/ApfsDir.h>
#include <ApfsLib/Device.h>
#include <cstdio>
#include <filesystem>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <vector>

static void require(bool ok, const char *why) {
    if (!ok) throw std::runtime_error(why);
}
static void write_new(const std::filesystem::path &path, const std::vector<uint8_t> &data) {
    FILE *f = fopen(path.c_str(), "wbx");
    require(f != nullptr, "Fresh output open failed");
    bool ok = fwrite(data.data(), 1, data.size(), f) == data.size();
    ok = fclose(f) == 0 && ok;
    require(ok, "Output write failed");
}
int main(int argc, char **argv) {
    try {
        require(argc == 3, "Usage: exporter fixed-image fresh-out-directory < image-paths.txt");
        const std::filesystem::path base("/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa");
        require(std::filesystem::canonical(argv[1]) == base/"out/root-mainline-v29/restore/restore-payload.bin", "Only fixed local restore image allowed");
        require(std::filesystem::is_regular_file(argv[1]), "Regular image required");
        auto output = std::filesystem::absolute(argv[2]).lexically_normal();
        auto relative = output.lexically_relative(base/"out");
        require(!relative.empty() && *relative.begin() != ".." && !std::filesystem::exists(output), "Fresh local out directory required");
        require(std::filesystem::canonical(output.parent_path()) == output.parent_path(), "Output parent must not redirect");
        std::unique_ptr<Device> device(Device::OpenDevice(argv[1]));
        require(bool(device), "Read-only image open failed");
        ApfsContainer container(device.get(), 0, device->GetSize());
        require(container.Init(), "APFS init failed");
        std::unique_ptr<ApfsVolume> volume(container.GetVolume(0));
        require(bool(volume), "APFS volume missing");
        ApfsDir dir(*volume);
        std::filesystem::create_directory(output);
        std::string line; unsigned index = 0;
        while (std::getline(std::cin, line)) {
            require(!line.empty() && line[0] == '/' && ++index <= 256, "Absolute bounded input paths required");
            uint64_t inode = 2;
            std::istringstream parts(line); std::string part;
            while (std::getline(parts, part, '/')) {
                if (part.empty()) continue;
                require(part != "." && part != "..", "No path traversal");
                ApfsDir::DirRec record;
                require(dir.LookupName(record, inode, part.c_str()), "Image path not found");
                inode = record.file_id;
            }
            ApfsDir::Inode meta; require(dir.GetInode(meta, inode), "Inode unavailable");
            require((meta.mode & 0170000) == 0100000, "Resolved regular image file required");
            std::vector<uint8_t> header, resource;
            bool has_header = dir.GetAttribute(header, inode, "com.apple.decmpfs");
            bool has_resource = dir.GetAttribute(resource, inode, "com.apple.ResourceFork");
            require(header.size() <= 1048576 && resource.size() <= 33554432, "Attribute size bound");
            auto prefix = output/std::to_string(index);
            if (has_header) write_new(prefix.string()+".decmpfs", header);
            if (has_resource) write_new(prefix.string()+".rsrc", resource);
            std::cout << index << '\t' << inode << '\t' << has_header << '\t' << has_resource << '\t' << line << '\n';
        }
        require(index != 0, "Empty input list");
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n'; return 1;
    }
}
