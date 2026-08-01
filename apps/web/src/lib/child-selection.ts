export type ChildSelectionOption = { id: string };

/** Resolve a URL child scope only against the parent's loaded Household children. */
export function resolveSelectedChildId(
  children: ChildSelectionOption[],
  requestedChildId: string | null,
) {
  if (
    requestedChildId &&
    children.some((child) => child.id === requestedChildId)
  ) {
    return requestedChildId;
  }
  return children[0]?.id ?? "";
}
