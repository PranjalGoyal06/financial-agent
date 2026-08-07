import type { Citation } from "../../lib/types";

type CitationListProps = {
  citations: Citation[];
};

export function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) {
    return (
      <details className="chat-citations">
        <summary>Citations</summary>
        <p className="chat-muted">No citations were returned for this response.</p>
      </details>
    );
  }

  return (
    <details className="chat-citations">
      <summary>Citations ({citations.length})</summary>
      <ol>
        {citations.map((citation) => (
          <li key={citation.evidence_id}>
            <div className="chat-citations__title">
              {citation.url ? (
                <a href={citation.url} target="_blank" rel="noreferrer">
                  {citation.title || citation.evidence_id}
                </a>
              ) : (
                citation.title || citation.evidence_id
              )}
            </div>
            {citation.source ? <div className="chat-muted">{citation.source}</div> : null}
            {citation.excerpt ? <p>{citation.excerpt}</p> : null}
          </li>
        ))}
      </ol>
    </details>
  );
}

