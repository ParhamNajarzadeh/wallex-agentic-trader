import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "موتور معاملاتی چند-ایجنته والکس (Wallex Agentic AI Trader)",
  description: "داشبورد تحلیلی و کنترل ریسک هکاتون والکس استارکوچ",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fa" dir="rtl">
      <body className="bg-slate-950 text-slate-100 antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}
