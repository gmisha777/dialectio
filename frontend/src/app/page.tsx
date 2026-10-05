import WorldMap from "@/components/WorldMap";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      <header className="flex items-center gap-4 border-b border-black/10 px-4 py-3 dark:border-white/15">
        <h1 className="text-xl font-semibold">Dialectio</h1>
        <input
          type="search"
          placeholder="Введіть слово…"
          aria-label="Пошук слова"
          disabled
          className="w-full max-w-md rounded-md border border-black/15 bg-transparent px-3 py-1.5 dark:border-white/20"
        />
      </header>
      <section className="relative flex-1">
        <WorldMap />
      </section>
    </main>
  );
}
