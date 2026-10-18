const FOOTER =
  "Built for Graph Hacks with FalkorDB · Decision support for genetic counsellors. Not medical advice. · ClinVar data: NCBI monthly archives, public · People, families, clinicians and organisations shown are fictional.";

export function SiteFooter() {
  return (
    <footer className="border-t border-black/10 px-4 py-4 text-sm text-[var(--color-muted)]">
      {FOOTER}
    </footer>
  );
}
