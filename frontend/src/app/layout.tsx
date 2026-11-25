/* eslint-disable @next/next/no-page-custom-font */
import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "ExamPulse AI | Constraint-Aware Agentic RAG Study Companion",
  description:
    "Upload your prescribed syllabus and PYQs to prioritize high-weightage exam topics, solve numericals, take auto-graded quizzes, and export 1-page cheat sheets.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-[#FFFCF5] font-sans text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
