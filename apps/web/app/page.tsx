export default function HomePage() {
  return (
    <main>
      <h1 className="text-3xl text-balance sm:text-4xl">When ClinVar changes, who must be told?</h1>
      <p className="mt-3 max-w-2xl text-[var(--color-muted)]">
        Real ClinVar submissions, diffed month by month inside FalkorDB. Pick any lab to see the
        classifications it changed.
      </p>
    </main>
  );
}
