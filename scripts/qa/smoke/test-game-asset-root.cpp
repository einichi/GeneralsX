// GeneralsX @bugfix Codex 11/10/2026 Regression coverage for Steam and EA retail data roots.
#include "StdDevice/Common/GameAssetRoot.h"
#include <cassert>
#include <fstream>
#include <iostream>

namespace fs = std::filesystem;
static void marker(const fs::path& file)
{
    fs::create_directories(file.parent_path());
    std::ofstream(file).put('\0');
}

int main(int argc, char** argv)
{
    assert(argc >= 2);
    const fs::path root = argv[1];
    const auto ea = root / "EA bundle";
    const auto zh = ea / "Command and Conquer Generals Zero Hour";
    const auto generals = ea / "Command and Conquer Generals";
    marker(zh / "INIZH.big");
    marker(zh / "MapsZH.big");
    marker(generals / "INI.big");
    marker(generals / "Maps.big");
    marker(zh / "ZH_Generals" / "INI.big");
    marker(zh / "ZH_Generals" / "Maps.big");
    marker(zh / "Mods" / "custom.big");
    marker(zh / "Mods" / "INIZH.big");
    assert(GameAssetRoot::resolve(ea, true) == zh);
    assert(GameAssetRoot::resolve(ea, false) == generals);
    assert(GameAssetRoot::resolve(zh, true) == zh);
    assert(GameAssetRoot::resolve(generals, false) == generals);
    assert(GameAssetRoot::resolve(generals, true).empty());
    // A ZH installation can supply its bundled base game when explicitly requested.
    assert(GameAssetRoot::resolve(zh, false) == zh / "ZH_Generals");
    assert(GameAssetRoot::isNestedInstallation(zh / "ZH_Generals" / "INI.big", zh));
    assert(!GameAssetRoot::isNestedInstallation(zh / "Mods" / "custom.big", zh));
    assert(!GameAssetRoot::isNestedInstallation(zh / "INIZH.big", zh));
    assert(!GameAssetRoot::isNestedInstallation(zh / "ZH_Generals" / "INI.big", zh / "ZH_Generals"));
    const auto steam = root / "Steam ZH";
    marker(steam / "inizh.BIG");
    marker(steam / "ZH_Generals" / "INI.big");
    marker(steam / "ZH_Generals" / "Maps.big");
    assert(GameAssetRoot::resolve(steam, true) == steam);
    marker(ea / "second Zero Hour" / "INIZH.big");
    marker(ea / "second Zero Hour" / "MapsZH.big");
    assert(GameAssetRoot::resolve(ea, true).empty());
    assert(GameAssetRoot::resolve(ea, false) == generals);
    const auto custom = root / "Custom";
    marker(custom / "Mods" / "custom.big");
    marker(custom / "Mods" / "INIZH.big");
    assert(GameAssetRoot::resolve(custom, true) == custom);
    assert(GameAssetRoot::resolve(root / "missing", true).empty());
    const auto baseOnly = root / "base-only bundle";
    marker(baseOnly / "Generals" / "INI.big");
    marker(baseOnly / "Generals" / "Maps.big");
    assert(GameAssetRoot::resolve(baseOnly, true).empty());
    assert(GameAssetRoot::resolve(baseOnly, false) == baseOnly / "Generals");
    // A direct root wins even if backup installations are present below it.
    marker(steam / "Backup" / "INIZH.big");
    marker(steam / "Backup" / "MapsZH.big");
    assert(GameAssetRoot::resolve(steam, true) == steam);
    assert(GameAssetRoot::isNestedInstallation(steam / "Backup" / "INIZH.big", steam));
    // Installed data is inspected without creating or changing any files there.
    if (argc == 3) {
        const auto actual = GameAssetRoot::resolve(argv[2], true);
        assert(!actual.empty() && GameAssetRoot::hasMarker(actual, "inizh.big"));
        assert(fs::is_regular_file(actual / "Data/Scripts/SkirmishScripts.scb"));
        assert(fs::is_regular_file(actual / "Data/Scripts/MultiplayerScripts.scb"));
        std::cout << "Installed Zero Hour root: " << actual << '\n';
    }
    std::cout << "Game asset root regressions passed\n";
}
