import "~/styles/globals.css"
import "@radix-ui/themes/styles.css"

import { Inter } from "next/font/google"


import { Container, Flex, Theme, ThemePanel } from "@radix-ui/themes"
import TabsSelect from "./Nav"
import { Toaster } from "~/shadcn/Sonner"
export const runtime = "edge"

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
})

export const metadata = {
  title: "Financial Tools",
  description: "Created by TJW",
  icons: [{ rel: "icon", url: "/favicon.ico" }],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark" style={{ colorScheme: "dark" }}>
      <body className={`font-sans ${inter.variable}`}>
        <Theme appearance="dark">
          <div className="flex min-h-screen flex-col">
            <span className="py-4 sm:py-8" />
            <TabsSelect />
            <main className="flex-1">
              <Container size="3" p="2">
                <Flex direction="column" align="center" gap="4">
                  {children}
                </Flex>
              </Container>
            </main>
            {/* <Footer /> */}
            <Toaster />
          </div>
        </Theme>
      </body>
    </html>
  )
}
