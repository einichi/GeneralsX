#!/usr/bin/env python3
"""Compile and run asset-root and match-error regressions without a full engine build.

Requires a C++17 compiler (CXX or clang++). Uses actual production headers and
extracts the two games' startup/parser functions, with small fault-injection
doubles for engine subsystems. This does not replace an in-game smoke test.
Usage: test-game-data-errors.py [--asset-root PATH]
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def function(source: Path, signature: str) -> str:
    text = source.read_text()
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
        end += 1
    return text[start:end]


SUPPORT = r'''
#pragma once
#include <cassert>
#include <cstdio>
#include <cstdarg>
#include <string>
#include <vector>
#include <stdexcept>
using Bool = bool; using Int = int;
#define FALSE false
#define TRUE true
#define MAX_PLAYER_COUNT 16
#define DEBUG_ASSERTCRASH(a,b) assert(a)
#define newInstance(T) new T
#define deleteInstance(p) delete p
class AsciiString {
    std::string value;
public:
    AsciiString(const char* text = "") : value(text) {}
    const char* str() const { return value.c_str(); }
    bool isNotEmpty() const { return !value.empty(); }
    void set(const char* text) { value = text; }
    void concat(const AsciiString& text) { value += text.str(); }
    bool operator==(const char* text) const { return value == text; }
    void format(const char* fmt, ...) {
        char buffer[8192]; va_list args; va_start(args, fmt);
        vsnprintf(buffer, sizeof(buffer), fmt, args); va_end(args); value = buffer;
    }
};
enum ErrorCode { ERROR_CORRUPT_FILE_FORMAT, ERROR_OTHER };
class DataChunkInput;
struct DataChunkInfo { AsciiString label; };
class ScriptList {
public:
    static int live, s_numInReadList;
    static ScriptList* s_readLists[MAX_PLAYER_COUNT];
    bool scripted = false;
    void* getScript() { return scripted ? this : nullptr; }
    void* getScriptGroup() { return nullptr; }
    ScriptList() { ++live; } ~ScriptList() { --live; }
    static Bool ParseScriptsDataChunk(DataChunkInput&, DataChunkInfo*, void*);
    static Bool ParseScriptListDataChunk(DataChunkInput&, DataChunkInfo*, void*) { return true; }
    static Int getReadScripts(ScriptList* [MAX_PLAYER_COUNT]);
};
int ScriptList::live = 0, ScriptList::s_numInReadList = 0;
ScriptList* ScriptList::s_readLists[MAX_PLAYER_COUNT] = {};
struct TScriptListReadInfo { int numLists; ScriptList* readLists[MAX_PLAYER_COUNT]; };
class DataChunkInput {
public:
    int failure = 0;
    template<class T> void registerParser(const char*, const AsciiString&, T) {}
    Bool parse(void* data) {
        if (!data) {
            DataChunkInfo info;
            return ScriptList::ParseScriptsDataChunk(*this, &info, this);
        }
        auto* lists = static_cast<TScriptListReadInfo*>(data);
        for (int i=0; i<3; ++i) lists->readLists[lists->numLists++] = new ScriptList;
        if (failure == 1) return false;
        if (failure == 2) throw ERROR_CORRUPT_FILE_FORMAT;
        if (failure == 3) throw ERROR_OTHER;
        return true;
    }
};
'''

STARTUP_SUPPORT = r'''
std::vector<std::string> events;
struct UnicodeString { void translate(const AsciiString&) {} };
struct Globals { bool m_headless = false, m_loadScreenRender = true; AsciiString m_initialFile; };
Globals global;
Globals *TheGlobalData = &global, *TheWritableGlobalData = &global;
struct LocalFS { AsciiString getAssetRootPath() { return "/game/data"; } } localFS;
LocalFS* TheLocalFileSystem = &localFS;
struct Engine { void setQuitting(bool) { events.push_back("quit"); } } engine;
Engine* TheGameEngine = &engine;
struct Shell {
    void reset() { events.push_back("shell-reset"); }
    void push(const char*) { events.push_back("menu"); }
    void showShell() { events.push_back("show-menu"); }
} shell;
Shell* TheShell = &shell;
struct GameText { UnicodeString fetch(const char*) { return {}; } } gameText;
GameText* TheGameText = &gameText;
void MessageBoxOk(UnicodeString, UnicodeString, void*) { events.push_back("dialog"); }
struct QuitGameException {};
struct Team { bool active = false; void setActive() { active = true; } } team;
struct TeamFactory { Team* found = nullptr; Team* findTeam(const AsciiString&) { return found; } } factory;
TeamFactory* TheTeamFactory = &factory;
class Player {
public:
    AsciiString m_playerName = "SkirmishChina1";
    Team* m_defaultTeam = nullptr;
    void setDefaultTeam();
};
const int TheKey_playerFaction = 0;
struct Dict { AsciiString getAsciiString(int) { return "FactionChina"; } } dict;
struct TestSide {
    ScriptList* scripts = nullptr;
    Dict* getDict() { return &dict; }
    ScriptList* getScriptList() { return scripts; }
};
struct CachedFileInputStream {
    static bool available; static int opens;
    bool open(const AsciiString&) { ++opens; return available; }
};
bool CachedFileInputStream::available = false;
int CachedFileInputStream::opens = 0;
class SidesList {
public:
    int m_numSides = 1;
    TestSide m_sides[1];
    void prepareForMP_or_Skirmish();
};
class GameLogic {
public:
    bool m_startNewGame = true, m_quitToDesktopAfterMatch = false, loading = true;
    int failure = 1;
    void tryStartNewGame(bool) {
        if (failure == 1) throw GameDataError("Data/Scripts/SkirmishScripts.scb", "Missing scripts");
        if (failure == 2) throw QuitGameException();
        events.push_back("started");
    }
    void deleteLoadScreen() { events.push_back("delete-load-screen"); }
    void setLoadingMap(bool value) { loading = value; }
    void setLoadingSave(bool value) { assert(!value); }
    void clearGameData(bool score) { assert(!score); events.push_back("clear-game"); }
    void startNewGame(Bool);
};
'''

MAIN = r'''
int main() {
    Player player;
    try { player.setDefaultTeam(); assert(false); } catch (const GameDataError&) {}
    assert(!player.m_defaultTeam);
    factory.found = &team; player.setDefaultTeam();
    assert(player.m_defaultTeam == &team && team.active);
    SidesList sides;
    try { sides.prepareForMP_or_Skirmish(); assert(false); } catch (const GameDataError&) {}
    assert(CachedFileInputStream::opens == 1);
    CachedFileInputStream::available = true; sides.prepareForMP_or_Skirmish();
    assert(CachedFileInputStream::opens == 2);
    ScriptList mapScripts; mapScripts.scripted = true; sides.m_sides[0].scripts = &mapScripts;
    CachedFileInputStream::available = false; sides.prepareForMP_or_Skirmish();
    assert(CachedFileInputStream::opens == 2);
    const int baselineLive = ScriptList::live;
    DataChunkInput file;
    for (int failure : {1, 2, 3}) {
        file.failure = failure;
        bool caught = false;
        try { parseRequiredScriptFile(file, nullptr, "scripts.scb"); }
        catch (const GameDataError&) { assert(failure != 3); caught = true; }
        catch (ErrorCode error) { assert(error == ERROR_OTHER && failure == 3); caught = true; }
        assert(caught && ScriptList::live == baselineLive && ScriptList::s_numInReadList == 0);
    }
    file.failure = 0;
    parseRequiredScriptFile(file, nullptr, "scripts.scb");
    ScriptList* scripts[MAX_PLAYER_COUNT];
    assert(ScriptList::getReadScripts(scripts) == 3);
    for (int i=0; i<3; ++i) delete scripts[i];
    assert(ScriptList::live == baselineLive);
    GameLogic logic;
    logic.startNewGame(false);
    assert(!logic.loading && !logic.m_startNewGame && !global.m_loadScreenRender);
    assert((events == std::vector<std::string>{"delete-load-screen", "clear-game", "shell-reset", "menu", "show-menu", "dialog"}));
    events.clear(); logic.failure = 0; logic.startNewGame(false);
    assert((events == std::vector<std::string>{"started"}));
    events.clear(); logic.failure = 1; global.m_headless = true;
    try { logic.startNewGame(false); assert(false); } catch (const GameDataError&) {}
    assert(events.empty()); global.m_headless = false; global.m_initialFile = "map";
    try { logic.startNewGame(false); assert(false); } catch (const GameDataError&) {}
    assert(events.empty()); global.m_initialFile = "";
    logic.failure = 2; logic.m_quitToDesktopAfterMatch = true; logic.startNewGame(false);
    assert((events == std::vector<std::string>{"quit"}));
    puts("Script failure cleanup and match recovery regressions passed");
}
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path)
    args = parser.parse_args()
    compiler = os.environ.get("CXX", "clang++")
    with tempfile.TemporaryDirectory(prefix="gx-data-tests-") as temp:
        work = Path(temp)
        binary = work / "root-test"
        subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        "-I", str(ROOT / "Core/GameEngineDevice/Include"),
                        str(Path(__file__).with_name("test-game-asset-root.cpp")), "-o", str(binary)], check=True)
        command = [str(binary), str(work / "assets")]
        if args.asset_root:
            command.append(str(args.asset_root))
        subprocess.run(command, check=True)
        (work / "support.h").write_text(SUPPORT)
        for header in ["Common/AsciiString.h", "Common/Errors.h", "Common/GameMemory.h", "Common/DataChunk.h", "GameLogic/Scripts.h"]:
            target = work / header
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('#include "support.h"\n')
        for variant in ["Generals", "GeneralsMD"]:
            source = ROOT / variant / "Code/GameEngine/Source"
            script_file = source / "GameLogic/ScriptEngine/Scripts.cpp"
            code = '#include "support.h"\n#include "Common/GameDataError.h"\n#include "GameLogic/RequiredScriptFile.h"\n'
            code += function(script_file, "Bool ScriptList::ParseScriptsDataChunk(") + "\n"
            code += function(script_file, "Int ScriptList::getReadScripts(") + "\n"
            code += STARTUP_SUPPORT
            code += function(source / "Common/RTS/Player.cpp", "void Player::setDefaultTeam(") + "\n"
            preflight = function(ROOT / "Core/GameEngine/Source/GameLogic/Map/SidesList.cpp",
                                 "void SidesList::prepareForMP_or_Skirmish(")
            code += preflight.split("\n\tm_skirmishTeamrec.clear();", 1)[0] + "\n}\n"
            code += function(source / "GameLogic/System/GameLogic.cpp", "void GameLogic::startNewGame(") + "\n" + MAIN
            test_source = work / f"{variant}.cpp"
            test_source.write_text(code)
            binary = work / variant
            subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Wno-unused-parameter",
                            "-I", str(work), "-I", str(ROOT / "Core/GameEngine/Include"),
                            str(test_source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
            print(f"{variant}: passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
