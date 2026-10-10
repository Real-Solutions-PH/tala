/** Screen title in the display style: regular words with the last word bold ("Mga **gamot**"). */
export function DisplayTitle({ children }: { children: string }) {
  const i = children.trimEnd().lastIndexOf(' ')
  if (i < 0) return <h1 className="display-title"><strong>{children}</strong></h1>
  return <h1 className="display-title">{children.slice(0, i + 1)}<strong>{children.slice(i + 1)}</strong></h1>
}
