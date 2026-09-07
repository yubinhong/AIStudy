import LearningHistoryPage from "../learning-history-page";

export default function MathLearningHistoryPage({
  searchParams,
}: {
  searchParams?: Promise<{ child?: string; date?: string }>;
}) {
  return <LearningHistoryPage searchParams={searchParams} subject="math" />;
}
