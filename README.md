# WorkBuddy · Claw 工作区

老张个人协作开发工作区。

## 用途

- WorkBuddy 桌面端 + CodeBuddy CLI + CodeBuddy IDE 的协同开发主目录
- 项目级文档、笔记、脚本、配置的统一落脚点

## 工作流

- 文档与配置：直接编辑提交
- 项目代码：在子目录里 `git init` 各自的子仓库（如需独立版本管理）
- AI 协同：WorkBuddy 会话内驱动 / CodeBuddy CLI 跑非交互任务 / VS Code + CodeBuddy 插件做 IDE 侧

## 目录约定

- `.workbuddy/memory/` —— 项目工作日志（每日追加）
- `.workbuddy/skills/` —— 项目级 skills（团队共享）
- 根目录文件 —— 通用配置（.gitignore、README、CI 等）

## 维护

保持整洁，避免把临时文件（下载物、二进制产物）误提交。临时脚本放 `.workbuddy/tmp/`，已被 `.gitignore` 屏蔽。