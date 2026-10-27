// <BrandList />: filter, sort and page through brands-api, with the view kept in the page URL.
import { useEffect, useRef } from "react";
import { BrandCard } from "./BrandCard";
import { Filters, Pager, Sort } from "./Controls";
import { Empty, ErrorState, LiveRegion, Loading } from "./States";
import type { MountConfig } from "./types";
import { useBrandList } from "./useBrandList";
import { hrefFor, useUrlState } from "./url-state";

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

  // Clear and Retry remove the button that was clicked, so focus goes to the heading once the
  // reload settles, whatever it shows.
  const focusAfterLoad = useRef(false);
  const reload = (load: () => void) => {
    focusAfterLoad.current = true;
    load();
  };
  useEffect(() => {
    if (result.status !== "loading" && focusAfterLoad.current) {
      focusAfterLoad.current = false;
      heading.current?.focus();
    }
  }, [result.status]);

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
          <ErrorState
            error={result.error}
            onRetry={() => reload(result.retry)}
            firstPage={
              state.page > 1
                ? {
                    href: hrefFor({ ...state, page: 1 }, config),
                    onClick: () => goToPage(1),
                  }
                : undefined
            }
          />
        )}
        {result.status === "success" && result.data.count === 0 && (
          <Empty
            onClear={
              state.industries.length > 0
                ? () => reload(() => navigate({ industries: [] }))
                : undefined
            }
          />
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
