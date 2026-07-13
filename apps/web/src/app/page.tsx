import { loadDemoChildren, readString } from "@/lib/demo-profile";

export default async function HomePage() {
  const children = await loadDemoChildren();
  const firstChild = children[0];

  return (
    <main>
      <p className="eyebrow">P0 基础骨架</p>
      <h1>家庭 AI 学习助手</h1>
      <p>
        Web/PWA 入口已接入共享 OpenAPI
        合同，家长和内容维护功能将继续沿家庭边界扩展。
      </p>
      <section aria-labelledby="profile-heading">
        <h2 id="profile-heading">孩子档案演示</h2>
        {firstChild ? (
          <p>
            {readString(firstChild, "display_name") ?? "合成孩子"} ·{" "}
            {readString(firstChild, "curriculum_version") ?? "数学演示教材"}
          </p>
        ) : (
          <p>API 尚未连接；启动 API 后刷新页面查看合成档案。</p>
        )}
      </section>
    </main>
  );
}
