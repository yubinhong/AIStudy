"use client";

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type LearningTrendPoint = {
  label: string;
  questions: number;
  hints: number;
};

export function LearningTrendChart({ data }: { data: LearningTrendPoint[] }) {
  return (
    <div className="trend-chart" aria-label="最近七天题目与提示次数趋势图">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={data}
          margin={{ top: 18, right: 8, bottom: 0, left: -24 }}
        >
          <CartesianGrid
            stroke="#e8eee9"
            strokeDasharray="3 3"
            vertical={false}
          />
          <XAxis
            axisLine={false}
            dataKey="label"
            fontSize={12}
            tick={{ fill: "#75857d" }}
            tickLine={false}
          />
          <YAxis
            allowDecimals={false}
            axisLine={false}
            fontSize={11}
            tick={{ fill: "#91a098" }}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "#ffffff",
              border: "1px solid #dce6df",
              borderRadius: 10,
              boxShadow: "0 10px 28px rgba(25, 50, 41, 0.08)",
              fontSize: 12,
            }}
            formatter={(value, name) => [
              Number(value),
              name === "questions" ? "确认题目" : "提示次数",
            ]}
          />
          <Legend
            iconType="circle"
            wrapperStyle={{ color: "#5d6f66", fontSize: 12, paddingTop: 12 }}
            formatter={(value) =>
              value === "questions" ? "确认题目" : "提示次数"
            }
          />
          <Bar dataKey="questions" fill="#cfe8d8" radius={[5, 5, 0, 0]} />
          <Line
            dataKey="hints"
            dot={{ fill: "#157a55", r: 3, strokeWidth: 0 }}
            stroke="#157a55"
            strokeWidth={2.5}
            type="monotone"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
