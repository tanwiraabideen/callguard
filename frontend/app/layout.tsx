import type { ReactNode } from "react";

export const metadata = {
  title: "CallGuard",
  description: "Real-time scam call copilot",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 32 }}>
        {children}
      </body>
    </html>
  );
}
