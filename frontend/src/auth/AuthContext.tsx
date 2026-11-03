import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, setSessionExpiredHandler } from "../api/client";
import { fetchMe, logoutRequest, updateLanguage, User } from "../api/auth";
import { clearTokens, loadLang, loadMode, loadTokens, Mode, saveMode, saveTokens, Tokens } from "../lib/storage";

type Status = "loading" | "signedOut" | "signedIn";

type AuthCtx = {
  status: Status;
  user: User | null;
  mode: Mode; // customer ya seller ke roop me app chal rahi hai
  setMode: (m: Mode) => Promise<void>;
  signIn: (tokens: Tokens) => Promise<void>;
  signOut: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<User | null>(null);
  const [mode, setModeState] = useState<Mode>("customer");

  const setMode = useCallback(async (m: Mode) => {
    setModeState(m);
    await saveMode(m);
  }, []);

  const signOut = useCallback(async () => {
    await logoutRequest();
    await clearTokens();
    await setMode("customer");
    setUser(null);
    setStatus("signedOut");
  }, [setMode]);

  const signIn = useCallback(async (tokens: Tokens) => {
    await saveTokens(tokens);
    let me = await fetchMe();
    const language = await loadLang();
    if (me.language !== language) {
      try {
        me = await updateLanguage(language);
      } catch {
        // Keep login working; the saved language is still sent with API requests.
      }
    }
    setUser(me);
    setStatus("signedIn");
  }, []);

  // App khulte hi: pehle se login hai ya nahi, aur kis roop me
  useEffect(() => {
    (async () => {
      setModeState(await loadMode());
      const tokens = await loadTokens();
      if (!tokens) return setStatus("signedOut");
      try {
        setUser(await fetchMe());
        setStatus("signedIn");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) await clearTokens();
        setStatus("signedOut");
      }
    })();
  }, []);

  // Refresh token bhi fail ho jaye to login par bhej do
  useEffect(() => {
    setSessionExpiredHandler(() => {
      setUser(null);
      setStatus("signedOut");
    });
  }, []);

  const value = useMemo(
    () => ({ status, user, mode, setMode, signIn, signOut }),
    [status, user, mode, setMode, signIn, signOut],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth ko AuthProvider ke andar use karo");
  return v;
}
