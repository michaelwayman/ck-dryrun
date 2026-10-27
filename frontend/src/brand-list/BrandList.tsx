// <BrandList />: filter, sort and page through brands-api, with the view kept in the page URL.
import { useRef } from "react";
import { BrandCard } from "./BrandCard";
import { Filters, Pager, Sort } from "./Controls";
import { Empty, ErrorState, LiveRegion, Loading } from "./States";
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
      <LiveRegion
        count={result.status === "success" ? result.data.count : null}
      />
      <div
        className="brand-list__results"
        aria-busy={result.status === "loading"}
      >
        {result.status === "loading" && <Loading />}
        {result.status === "error" && (
          <ErrorState error={result.error} onRetry={result.retry} />
        )}
        {result.status === "success" && result.data.count === 0 && (
          <Empty onClear={() => navigate({ industries: [] })} />
        )}
        {result.status === "success" && result.data.count > 0 && (
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
