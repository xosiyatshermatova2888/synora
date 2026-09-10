import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "SYNORA — Your restaurant. One intelligent system.";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: 80,
          background: "#080A0F",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 28 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 14,
              background: "linear-gradient(120deg,#7C5CFF,#35D6FF)",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 32,
              fontWeight: 800,
            }}
          >
            S
          </div>
          <div style={{ fontSize: 40, fontWeight: 700, color: "#F5F7FA" }}>SYNORA</div>
        </div>
        <div style={{ fontSize: 64, fontWeight: 700, color: "#F5F7FA", lineHeight: 1.15, maxWidth: 900 }}>
          Your restaurant.{" "}
          <span style={{ color: "#35D6FF" }}>One intelligent system.</span>
        </div>
        <div style={{ marginTop: 28, fontSize: 28, color: "#9AA3B2", maxWidth: 850 }}>
          AI-native Restaurant Operating System
        </div>
      </div>
    ),
    { ...size }
  );
}
