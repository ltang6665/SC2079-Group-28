import "@/styles/globals.css";
import Head from "next/head";
import Simulator from "components/Simulator";

export default function App({ Component, pageProps }) {
  return (
    <div data-theme="dark" className="bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-gray-900 via-gray-800 to-black h-screen overflow-auto">
      <Head>
        <title>MDP Group 20 Algo Simulator</title>
      </Head>
      <Simulator />
    </div>
  );
}
