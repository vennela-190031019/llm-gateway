/** Generic "couldn't load this data" banner for failed queries. */
export function ErrorNotice({ message }: { message: string }) {
  return (
    <div className="notice notice-error">
      <strong>Failed to load data:</strong> {message}
    </div>
  );
}
