import "./globals.css";
import AppProviders from "@/providers/AppProviders";

export const metadata = {
  title: "Avok Escrow",
  description: "Secure escrow-first marketplace payments for Ghana."
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
