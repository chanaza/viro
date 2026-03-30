export interface SearchResult {
  url: string;
  title: string;
  snippet: string;
}

export interface ClassifiedUrl {
  url: string;
  relevant: boolean;
  type: "api" | "pdf" | "html";
  priority: 1 | 2 | 3 | 4;
}

export interface ResultItem {
  name: string;
  city: string;
  address: string;
}
