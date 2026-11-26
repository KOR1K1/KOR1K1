// Collects one year of public and private activity into a plain data file.
// Everything the renderer draws comes from here, so the SVG stays reproducible
// from docs/data.json without a token.

export type Day = { date: string; count: number };

export type Project = {
  name: string;
  owner: string;
  url: string;
  lang: string | null;
  stars: number;
  fork: boolean;
  upstream: string | null;
  description: string;
  // date -> commits authored by the user that day, deduped across branches
  commits: Record<string, number>;
  prs: { date: string; title: string; state: string }[];
};

export type Data = {
  schema: 2;
  user: string;
  generatedAt: string;
  from: string;
  to: string;
  days: Day[];
  totals: {
    contributions: number;
    private: number;
    commits: number;
    prs: number;
    issues: number;
    stars: number;
  };
  projects: Project[];
};

const API = "https://api.github.com";

async function gh<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path.startsWith("http") ? path : API + path, {
    ...init,
    headers: {
      authorization: `bearer ${token}`,
      accept: "application/vnd.github+json",
      "user-agent": "exposure-readme",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error(`${res.status} ${path}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

async function graphql<T>(token: string, query: string, variables: object): Promise<T> {
  const body = await gh<{ data: T; errors?: unknown }>(token, "/graphql", {
    method: "POST",
    body: JSON.stringify({ query, variables }),
  });
  if (body.errors) throw new Error(JSON.stringify(body.errors));
  return body.data;
}

const QUERY = `
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      nodes {
        name isFork stargazerCount pushedAt description url
        owner { login }
        primaryLanguage { name }
        parent { nameWithOwner primaryLanguage { name } }
        refs(refPrefix: "refs/heads/", first: 20) { nodes { name } }
      }
    }
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
      pullRequestContributions(first: 100) {
        nodes {
          occurredAt
          pullRequest {
            title state
            repository {
              name isFork isPrivate stargazerCount description url
              owner { login }
              primaryLanguage { name }
            }
          }
        }
      }
    }
  }
}`;

type Repo = {
  name: string;
  isFork: boolean;
  stargazerCount: number;
  pushedAt: string;
  description: string | null;
  url: string;
  owner: { login: string };
  primaryLanguage: { name: string } | null;
  parent?: { nameWithOwner: string; primaryLanguage: { name: string } | null } | null;
  refs?: { nodes: { name: string }[] };
};

export async function fetchData(user: string, token: string, now = new Date()): Promise<Data> {
  const to = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const from = new Date(to.getTime() - 364 * 86400e3);
  const iso = (d: Date) => d.toISOString().slice(0, 10);

  const q = await graphql<any>(token, QUERY, {
    login: user,
    from: from.toISOString(),
    to: new Date(to.getTime() + 86400e3 - 1).toISOString(),
  });
  const cc = q.user.contributionsCollection;
  const repos: Repo[] = q.user.repositories.nodes;

  const days: Day[] = cc.contributionCalendar.weeks
    .flatMap((w: any) => w.contributionDays)
    .map((d: any) => ({ date: d.date, count: d.contributionCount }))
    .filter((d: Day) => d.date >= iso(from) && d.date <= iso(to));

  const projects = new Map<string, Project>();
  const key = (owner: string, name: string) => `${owner}/${name}`.toLowerCase();

  // Forks never show up in commitContributionsByRepository, so commits are
  // read per branch from REST for every repo pushed inside the window.
  for (const r of repos) {
    if (r.pushedAt < from.toISOString()) continue;
    if (r.name.toLowerCase() === user.toLowerCase()) continue;
    const commits: Record<string, number> = {};
    const seen = new Set<string>();
    for (const ref of r.refs?.nodes ?? []) {
      const url =
        `/repos/${r.owner.login}/${r.name}/commits?sha=${encodeURIComponent(ref.name)}` +
        `&author=${user}&since=${from.toISOString()}&per_page=100`;
      const list = await gh<any[]>(token, url).catch(() => []);
      for (const c of list) {
        if (seen.has(c.sha)) continue;
        seen.add(c.sha);
        const d = c.commit.author.date.slice(0, 10);
        commits[d] = (commits[d] ?? 0) + 1;
      }
    }
    if (!Object.keys(commits).length) continue;
    projects.set(key(r.owner.login, r.name), {
      name: r.name,
      owner: r.owner.login,
      url: r.url,
      lang: r.primaryLanguage?.name ?? r.parent?.primaryLanguage?.name ?? null,
      stars: r.stargazerCount,
      fork: r.isFork,
      upstream: r.parent?.nameWithOwner ?? null,
      description: r.description ?? "",
      commits,
      prs: [],
    });
  }

  for (const n of cc.pullRequestContributions.nodes) {
    const pr = n.pullRequest;
    const r = pr.repository;
    // Output is public. With a repo-scoped PAT this list includes private
    // repos; those must stay aggregate-only (calendar + restricted count).
    if (r.isPrivate) continue;
    const k = key(r.owner.login, r.name);
    if (!projects.has(k)) {
      projects.set(k, {
        name: r.name,
        owner: r.owner.login,
        url: r.url,
        lang: r.primaryLanguage?.name ?? null,
        stars: r.stargazerCount,
        fork: r.isFork,
        upstream: null,
        description: r.description ?? "",
        commits: {},
        prs: [],
      });
    }
    projects.get(k)!.prs.push({ date: n.occurredAt.slice(0, 10), title: pr.title, state: pr.state });
  }

  // A fork whose work landed as a PR upstream is one story, not two lanes:
  // keep the upstream identity and fold the fork's commits into it.
  for (const [k, p] of projects) {
    if (!p.fork || !p.upstream) continue;
    const up = projects.get(p.upstream.toLowerCase());
    if (!up) continue;
    for (const [d, c] of Object.entries(p.commits)) up.commits[d] = (up.commits[d] ?? 0) + c;
    if (!up.lang) up.lang = p.lang;
    projects.delete(k);
  }

  return {
    schema: 2,
    user,
    generatedAt: now.toISOString(),
    from: iso(from),
    to: iso(to),
    days,
    totals: {
      contributions: cc.contributionCalendar.totalContributions,
      private: cc.restrictedContributionsCount,
      commits: cc.totalCommitContributions,
      prs: cc.totalPullRequestContributions,
      issues: cc.totalIssueContributions,
      stars: repos.filter((r) => !r.isFork).reduce((s, r) => s + r.stargazerCount, 0),
    },
    projects: [...projects.values()],
  };
}
