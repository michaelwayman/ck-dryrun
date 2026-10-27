// <BrandList />: filter, sort and page through brands-api, with the view kept in the page URL.
import { useRef } from "react";
import { BrandCard } from "./BrandCard";
import { Filters, Pager, Sort } from "./Controls";
import type { MountConfig } from "./types";
import { useBrandList } from "./useBrandList";
import { useUrlState } from "./url-state";

export function BrandList({ config }: { config: MountConfig }) {
  const [state, navigate] = useUrlState(config);
  const result = useBrandList(state, config);
  const heading = useRef<HTMLHeadingElement>(null);

  // A new page replaces the list the user was reading, so focus goes to its heading. Filter and
  // sort keep focus on their control.
  const goToPage = (page: number) => {
    navigate({ page });
    heading.current?.focus();
  };

  return (
    <div className="brand-list">
      <div className="brand-list__controls">
        <Filters
          config={config}
          state={state}
          onChange={(industries) => navigate({ industries })}
        />
        <Sort
          ordering={state.ordering}
          onChange={(ordering) => navigate({ ordering })}
        />
      </div>
      <h2 className="brand-list__heading" ref={heading} tabIndex={-1}>
        Results
      </h2>
      <div className="brand-list__results">
        {result.status === "loading" && <p>Loading brands…</p>}
        {result.status === "error" && <p>{result.error.message}</p>}
        {result.status === "success" && (
          <>
            <div className="grid">
              {result.data.results.map((brand) => (
                <BrandCard key={brand.slug} brand={brand} />
              ))}
            </div>
            <Pager
              config={config}
              state={state}
              count={result.data.count}
              onPage={goToPage}
            />
          </>
        )}
      </div>
    </div>
  );
}
