export function ComingSoon({ title }: { title: string }) {
  return (
    <div className="page">
      <div className="page-header">
        <h1>{title}</h1>
      </div>
      <div className="empty-state">
        <p>{title} is coming in Phase 10b.</p>
        <p className="text-muted">This nav entry exists now so the app's navigation structure is complete.</p>
      </div>
    </div>
  );
}
