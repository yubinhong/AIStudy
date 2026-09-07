import LearningHistoryPage from "../learning-history-page";

export default function ChineseLearningHistoryPage({
  searchParams,
}: {
  searchParams?: Promise<{ child?: string; date?: string }>;
}) {
  return <LearningHistoryPage searchParams={searchParams} subject="chinese" />;
}
