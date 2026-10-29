// Minimal UI translation: a flat dictionary keyed by the English string, a
// React context, and a localStorage-backed language choice. No i18n library:
// the UI has a few dozen strings and two languages, so a lookup table is enough.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type Language = "en" | "vi";

const STORAGE_KEY = "datrose_language";

// English is the key and the fallback; only the other languages are listed.
const vi: Record<string, string> = {
  // Sidebar / shell
  Dashboard: "Bảng điều khiển",
  Profiles: "Hồ sơ",
  Diagnostics: "Chẩn đoán",
  Logs: "Nhật ký",
  "Engine ready": "Engine sẵn sàng",
  "Engine offline": "Engine ngoại tuyến",
  "Starting…": "Đang khởi động…",
  "Version {version} is available.": "Đã có bản {version}.",
  "Update now": "Cập nhật ngay",
  "Updating…": "Đang cập nhật…",

  // Dashboard
  "Live view of the engine.": "Xem trực tiếp trạng thái engine.",
  "Cannot reach the engine: {error}": "Không kết nối được engine: {error}",
  "Is the engine running? Check the Logs tab.": "Engine có đang chạy không? Xem tab Nhật ký.",
  "Waiting for the engine…": "Đang chờ engine…",
  "Preparing Dat-Rose…": "Đang chuẩn bị Dat-Rose…",
  Session: "Phiên",
  App: "Ứng dụng",
  Phase: "Giai đoạn",
  "Game mode": "Chế độ chơi",
  "Locked champion": "Tướng đã khóa",
  "Selected skin": "Skin đã chọn",
  "Historic mode": "Chế độ lịch sử",
  "Random mode": "Chế độ ngẫu nhiên",
  on: "bật",
  off: "tắt",
  "Enter a champ select to pick a skin.": "Vào chọn tướng để chọn skin.",
  "In champ select": "Đang trong chọn tướng",
  "Waiting for champ select": "Đang chờ vào chọn tướng",
  "Champion ID": "ID tướng",
  "No champion locked": "Chưa khóa tướng",
  "Selected skin: #{id}": "Skin đã chọn: #{id}",
  Downloads: "Tải xuống",
  Skins: "Skin",
  Previews: "Ảnh xem trước",
  ready: "sẵn sàng",
  pending: "đang chờ",

  // Profiles
  "One set of skin choices per League account.": "Mỗi tài khoản Liên Minh có một bộ chọn skin riêng.",
  "Current account": "Tài khoản hiện tại",
  "Signed in as {name}": "Đang đăng nhập: {name}",
  unknown: "không rõ",
  "Display name": "Tên hiển thị",
  "Save current account": "Lưu tài khoản hiện tại",
  "Open the League client to detect your account.": "Mở client Liên Minh để nhận diện tài khoản.",
  "Stored profiles": "Hồ sơ đã lưu",
  "No profiles yet.": "Chưa có hồ sơ nào.",
  Load: "Tải",
  Delete: "Xóa",
  active: "đang dùng",
  "Profile saved": "Đã lưu hồ sơ",
  "Profile loaded": "Đã tải hồ sơ",
  "Profile deleted": "Đã xóa hồ sơ",

  // Diagnostics
  "Problems the engine hit, and the versions it tracks.": "Các lỗi engine gặp phải và phiên bản đang theo dõi.",
  "App update": "Cập nhật ứng dụng",
  "Check for updates": "Kiểm tra cập nhật",
  "Install {version}": "Cài đặt {version}",
  Problems: "Vấn đề",
  "No problems reported.": "Không có vấn đề nào.",
  "Upstream versions": "Phiên bản nguồn",
  "Checking…": "Đang kiểm tra…",
  "Re-check": "Kiểm tra lại",
  "You are up to date.": "Bạn đang dùng bản mới nhất.",
  "Downloading update…": "Đang tải bản cập nhật…",
  "Downloading… {percent}%": "Đang tải… {percent}%",
  "Downloading…": "Đang tải…",
  "Update installed. Restarting…": "Đã cài đặt. Đang khởi động lại…",

  // Logs
  "Live engine output, newest at the bottom.": "Nhật ký engine trực tiếp, mới nhất ở dưới.",
  Refresh: "Làm mới",
  Auto: "Tự động",
  "No log output yet.": "Chưa có nhật ký.",

  // Failed skins
  "Failed skins": "Skin lỗi",
  "Skins that failed to download. Retry them individually.": "Các skin tải lỗi. Thử tải lại từng cái.",
  "No failed skins.": "Không có skin lỗi.",
  Retry: "Thử lại",
  "Retrying…": "Đang thử lại…",
  "Retry all": "Thử lại tất cả",
  "Retried {name}": "Đã thử lại {name}",
  "Retry failed: {error}": "Thử lại thất bại: {error}",
  "Champion {champion}": "Tướng {champion}",

  // Language switch
  Language: "Ngôn ngữ",
  English: "Tiếng Anh",
  "Tiếng Việt": "Tiếng Việt",
};

const dictionaries: Record<Language, Record<string, string>> = { en: {}, vi };

function translate(language: Language, text: string, vars?: Record<string, string | number>): string {
  const template = dictionaries[language][text] ?? text;
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, key) => (key in vars ? String(vars[key]) : match));
}

interface I18nValue {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (text: string, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

function readStoredLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "vi") return stored;
  } catch {
    // localStorage can be unavailable; fall back to English.
  }
  return "en";
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>(readStoredLanguage);

  const setLanguage = useCallback((next: Language) => {
    setLanguageState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Ignore storage failures; the choice just will not persist.
    }
  }, []);

  const value = useMemo<I18nValue>(
    () => ({ language, setLanguage, t: (text, vars) => translate(language, text, vars) }),
    [language, setLanguage],
  );

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside I18nProvider");
  return value;
}
