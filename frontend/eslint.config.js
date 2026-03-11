import tanstackEslintConfig from "@tanstack/eslint-config";

export default [
  ...tanstackEslintConfig({
    type: "app",
    node: true,
    browser: true,
    typescript: true,
    react: true,
  }),
  {
    rules: {
      "@typescript-eslint/no-unused-vars": "warn",
    },
  },
];
