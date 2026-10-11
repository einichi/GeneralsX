// GeneralsX @bugfix Codex 11/10/2026 Resolve retail bundle parents before mounting archives.
#pragma once

#include <filesystem>
#include <string>
#include <cctype>

namespace GameAssetRoot {
inline bool hasMarker(const std::filesystem::path& directory, const char* marker)
{
    std::error_code error;
    std::filesystem::directory_iterator entries(directory, error);
    for (auto end = std::filesystem::directory_iterator(); !error && entries != end; entries.increment(error)) {
        std::string name = entries->path().filename().string();
        for (char& c : name) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
        if (name == marker && entries->is_regular_file(error)) return true;
    }
    return false;
}

inline bool isRetailInstallation(const std::filesystem::path& directory, bool zeroHour)
{
    return hasMarker(directory, zeroHour ? "inizh.big" : "ini.big") &&
        hasMarker(directory, zeroHour ? "mapszh.big" : "maps.big");
}

// A direct installation wins. Only a unique immediate child of the requested edition is accepted.
// Custom roots without retail markers retain their existing archive/mod layout.
inline std::filesystem::path resolve(const std::filesystem::path& directory, bool zeroHour)
{
    const char* marker = zeroHour ? "inizh.big" : "ini.big";
    if (hasMarker(directory, marker)) return directory;
    std::error_code error;
    std::filesystem::directory_iterator entries(directory, error);
    std::filesystem::path selected;
    bool otherEdition = false;
    for (auto end = std::filesystem::directory_iterator(); !error && entries != end; entries.increment(error)) {
        if (entries->is_directory(error)) {
            otherEdition = otherEdition || isRetailInstallation(entries->path(), !zeroHour);
            if (!isRetailInstallation(entries->path(), zeroHour)) continue;
            if (!selected.empty()) return {}; // Ambiguous: require an explicit installation path.
            selected = entries->path();
        }
    }
    if (error) return {};
    if (!selected.empty()) return selected;
    // Never mount the other edition simply because it contains BIG files.
    if (otherEdition || hasMarker(directory, zeroHour ? "ini.big" : "inizh.big")) return {};
    return directory;
}

inline bool isNestedInstallation(const std::filesystem::path& archive, const std::filesystem::path& root)
{
    const auto absoluteRoot = std::filesystem::absolute(root).lexically_normal();
    if (!hasMarker(absoluteRoot, "inizh.big") && !hasMarker(absoluteRoot, "ini.big")) return false;
    auto parent = std::filesystem::absolute(archive).lexically_normal().parent_path();
    while (parent != absoluteRoot && parent != parent.parent_path()) {
        // A mod can contain an INI archive too; require retail map archives before isolating it.
        if (isRetailInstallation(parent, true) || isRetailInstallation(parent, false)) return true;
        parent = parent.parent_path();
    }
    return false;
}
}
