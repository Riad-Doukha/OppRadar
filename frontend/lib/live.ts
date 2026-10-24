"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { io } from "socket.io-client";

import { env } from "@/lib/env";
import { createClient } from "@/lib/supabase/client";

/**
 * Live updates over Socket.IO (backend app/sockets): a new match alert refreshes
 * the bell, notifications, feed and dashboard right away. Polling stays as the
 * fallback, so a dropped connection never loses anything.
 */
export function useLiveUpdates() {
  const qc = useQueryClient();
  useEffect(() => {
    let socket: ReturnType<typeof io> | null = null;
    let cancelled = false;
    createClient()
      .auth.getSession()
      .then(({ data }) => {
        if (cancelled || !data.session) return;
        socket = io(env.apiUrl, { path: "/ws/socket.io", auth: { token: data.session.access_token }, transports: ["websocket"] });
        socket.on("notification:new", () => {
          for (const key of ["notifications", "feed", "dashboard"]) qc.invalidateQueries({ queryKey: [key] });
        });
      });
    return () => {
      cancelled = true;
      socket?.disconnect();
    };
  }, [qc]);
}
