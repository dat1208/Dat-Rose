# D-Changer — kế hoạch xây app cá nhân dựa trên Rose

## Mục tiêu
App skin changer cá nhân cho League of Legends, dùng kỹ thuật + kiến trúc của Rose nhưng:
- Bỏ analytics hoàn toàn (offline-first, không telemetry)
- Desktop UI riêng (Tauri) thay vì chỉ tray + plugin client
- Updater đa nguồn: tự check mọi bên liên quan
- Auto-fetch LTK patcher (không cần user copy tay)
- Multi-account profile (lưu cấu hình skin theo account)
- An toàn nhất có thể: verify checksum, không đụng network/memory game

## Quyết định kiến trúc

### Giữ lại từ Rose (engine — phần khó, đã chạy)
| Module | Vai trò | Ghi chú |
|---|---|---|
| `lcu/` | LCU API client (lockfile, HTTP, websocket creds) | Giữ nguyên |
| `injection/core/injector.py` | Điều phối mkoverlay + LTK patcher | Giữ nguyên |
| `injection/overlay/overlay_manager.py` | mkoverlay + LTK patcher line protocol | Giữ nguyên |
| `injection/game/game_monitor.py` | Suspend/resume game process | Giữ nguyên |
| `injection/loadingname/loading_name.py` | Loading screen name (RST v5 + XXH3/XXH64) | Giữ nguyên |
| `injection/mods/` | Mod storage, zip resolver, modpkg | Giữ nguyên |
| `pengu/` | WebSocket bridge + message handler | Giữ, bỏ phần analytics hook |
| `threads/` | Phase/lock/timer/injection trigger | Giữ nguyên |
| `Pengu Loader/plugins/*` | JS plugins trong client | Giữ, bỏ ROSE-PartyMode nếu không dùng |

### Bỏ / thay
| Thành phần Rose | Thay bằng |
|---|---|
| `analytics/` | Xóa hẳn |
| `launcher/ui/update_dialog.py` (Win32 dialog) | Tauri window |
| `launcher/update/` (chỉ check Rose repo) | `updater/` đa nguồn |
| `utils/integration/tray_manager.py` | Tauri tray (native) |
| `main/setup/console.py` | Bỏ console, log ra file |
| LTK patcher "user tự copy" | `updater/ltk_patcher.py` auto-fetch |

### Kiến trúc mới
```
D-Changer/
├── backend/                  # Python (giữ từ Rose, gọn lại)
│   ├── lcu/                  # LCU client
│   ├── injection/            # engine inject (giữ nguyên)
│   ├── pengu/                # bridge + plugins host
│   ├── threads/              # phase/lock/timer
│   ├── state/                # shared state
│   ├── utils/                # paths, logging, download
│   ├── updater/              # MỚI: đa nguồn
│   │   ├── sources.py        # GitHub release/commit checker
│   │   ├── ltk_patcher.py    # MỚI: auto-fetch + extract patcher
│   │   ├── skin_sync.py      # LeagueSkins sync
│   │   └── verify.py         # checksum/signature verify
│   ├── profiles/             # MỚI: multi-account
│   └── api.py                # MỚI: HTTP/JSON API cho Tauri UI
├── ui/                       # MỚI: Tauri app
│   ├── src/                  # React/TS
│   └── src-tauri/            # Rust shell
├── Pengu Loader/             # plugins JS (giữ)
├── vendor/                   # PenguLoader source (giữ)
└── config.py                 # bỏ analytics constants
```

## Updater đa nguồn — các bên cần check

| Nguồn | API | Chu kỳ | Hành động |
|---|---|---|---|
| LTK Manager | `repos/LeagueToolkit/ltk-manager/releases/latest` | 24h | Nếu patcher EOL → tải installer mới, extract |
| LeagueSkins | `repos/Alban1911/LeagueSkins/commits/main` | mỗi lần start | Sync skin mới (incremental) |
| PenguLoader | `repos/PenguLoader/PenguLoader/releases/latest` | 7 ngày | Cảnh báo nếu có bản mới hơn vendored |
| Rose upstream | `repos/Alban1911/Rose/commits/main` | 7 ngày | Cảnh báo kỹ thuật mới để port |
| D-Changer self | repo riêng của bạn | mỗi start | Auto-update app |

### LTK patcher auto-fetch — luồng
```
1. check_ltk_patcher(tools_dir) → nếu thiếu hoặc EOL:
2. GET releases/latest → lấy asset LTK.Manager_<ver>_x64-setup.exe
3. Tải installer (verify sha256 từ digest asset API nếu có)
4. Chạy silent install vào temp dir:
   LTK.Manager_<ver>_x64-setup.exe /S /D=<temp>
   (NSIS: /S silent, /D= install dir — phải để cuối, không quote)
5. Copy ltk_patcher_host.exe + ltk_patcher_dll.dll từ temp → tools_dir
6. Verify: check_ltk_patcher lại, đọc EOL date, so với game build
7. Xóa temp
```
Fallback nếu silent install fail: hướng dẫn user cài LTK Manager thủ công, dò install dir.

## An toàn (bắt buộc, không cắt)
- Mọi download: verify SHA-256 (từ GitHub asset `digest` field) trước khi dùng
- Bridge chỉ bind `127.0.0.1`, chặn origin ngoài loopback (đã có ở Rose)
- Extract archive: dùng `safe_extract`, chặn path traversal + zip bomb
- Không gửi bất kỳ dữ liệu nào ra ngoài (bỏ analytics)
- Dependency pin version, CI check
- Không đụng memory/network game — chỉ render client-side như Rose

## Giai đoạn triển khai

### Phase 1 — Nền tảng (làm được ngay)
1. Tạo cấu trúc thư mục `backend/`, copy engine từ Rose
2. Bỏ `analytics/`, bỏ `party/` + `relay-worker/`, dọn `config.py`
3. **Tối ưu startup**: gộp hash check, song song hóa, bỏ blocking WS/Pengu (mục "Nâng cấp engine")
4. Viết `updater/sources.py` + `updater/verify.py`
5. Viết `updater/ltk_patcher.py` (auto-fetch)
6. Viết `api.py` (HTTP JSON cho UI)
7. Viết `profiles/` (multi-account)

**Trạng thái Phase 1:** 1-2, 4-7 xong (backend/ chạy được, 219 test pass, lint sạch,
CI có job `backend`). Mục 3 (tối ưu startup) xong: hash check gộp 1 call + cache TTL 6h,
hash/patcher/skin chạy song song trong launcher, Pengu activate + injection setup chuyển
sang background (main loop chạy ngay), có timing log `[Startup]`.

### Phase 2 — UI
8. Tauri app: dashboard, skin library, settings, diagnostics
9. Tray native + start/stop backend
10. Multi-account profile (module `profiles/` đã xong ở Phase 1; UI còn thiếu)

**Trạng thái Phase 2:** 8 xong (Tauri v2 + React/TS: dashboard, profiles,
diagnostics), 9 một phần (Rust shell tự start/stop backend sidecar; tray native
chưa làm — engine vẫn dùng tray cũ), 10 xong (UI profiles nối `api.py`).

### Phase 3 — Hoàn thiện
11. Build script (PyInstaller backend + Tauri bundle)
12. Test end-to-end với League
13. CI: lint, test, verify checksum (backend job đã có; Tauri job còn thiếu)

**Trạng thái Phase 3:** 11 xong (`scripts/build_dchanger.py` + `backend/D-Changer.spec`),
13 xong (CI thêm job `backend` và `ui`). 12 còn lại — cần chạy thật với League.

## Nâng cấp engine — giảm thời gian load (vấn đề user nêu)

### Nguyên nhân chậm (đã phân tích code Rose)
Startup chạy tuần tự, blocking, nhiều network round-trip:
| Bước | Chi phí | File |
|---|---|---|
| Update check | 1 API call | `launcher/update/github_client.py:32` |
| **Hash check** | **9 API call tuần tự** + tải 9 file nếu update | `utils/download/hash_updater.py:120,290` |
| Skin sync | 1 SHA check + có thể tải cả repo ZIP | `utils/download/repo_downloader.py` |
| Pengu activation | Chờ restart client nếu đang mở | `utils/integration/pengu_loader.py` |
| Chờ WS connect | `while not is_connected: sleep(0.1)` | `main/__init__.py:680` |
| Injection init | Detect game path, list process | `main/core/initialization.py:83` |

### Kế hoạch tối ưu (thứ tự lợi ích/công)
1. **Gộp + cache hash check**: 9 API call → 1 call (`commits?path=hashes/lol&per_page=1`), cache TTL 6h. Chạy hash/skin/update check **song song** (ThreadPoolExecutor).
2. **Bỏ blocking startup**: main loop chạy ngay; injection init qua callback khi WS ready; defer Pengu client restart tới lobby.
3. **Lazy skin sync**: sync nền sau khi app lên; tải skin on-demand khi user chọn.
4. **Hash file cache mạnh hơn**: chỉ re-check khi file cũ hơn N ngày.
5. **Startup timing log**: đo từng bước để xác định điểm chậm trên máy cụ thể.

### Kỳ vọng
Startup từ ~10-40s → **~2-5s**. Đây là nâng cấp engine lớn nhất, làm ở Phase 1.

## Rủi ro đã biết
- **LTK patcher silent install**: NSIS `/D=` có thể fail nếu installer cần admin (perMachine). Cần test thực tế; fallback dò install dir.
- **Vanguard**: giữ nguyên cách Rose né (client-side render only). Không thêm gì đụng memory game.
- **Pengu Loader version**: vendored 1.1.6, nếu upstream ra mới hơn cần build lại.
- **Đây là app cá nhân**: không phân phối, nên rủi ro DMCA thấp.

## Việc cần bạn xác nhận
- Tên app: `D-Changer`? (hay tên khác)
- ~~Party Mode~~ → **bỏ** (đã chốt)
- ~~ROSE-Jade~~ → **bỏ** (chỉ là cosmetic client, không cần)
- UI: Tauri (Rust+React) — đã chốt, đẹp + nhẹ
