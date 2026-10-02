import './globals.css';
import AuthGate from '@/components/AuthGate';
export const metadata = { title: 'MoveWise', description: 'Your relocation workspace' };
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body><AuthGate>{children}</AuthGate></body></html>; }
