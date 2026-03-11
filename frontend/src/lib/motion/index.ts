/**
 * Framer Motion UI Components
 *
 * Pre-typed motion wrappers for common HTML elements.
 * These provide ergonomic access to framer-motion with proper TypeScript types.
 */

import { motion } from "framer-motion";
import type { ComponentPropsWithoutRef, ElementType } from "react";

/**
 * Helper type for motion component props
 */
type MotionComponentProps<T extends ElementType> = ComponentPropsWithoutRef<
  (typeof motion)[T & keyof typeof motion]
>;

// Export common motion components with proper typing
export const MotionDiv = motion.div as React.FC<MotionComponentProps<"div">>;
export const MotionSection = motion.section as React.FC<
  MotionComponentProps<"section">
>;
export const MotionArticle = motion.article as React.FC<
  MotionComponentProps<"article">
>;
export const MotionNav = motion.nav as React.FC<MotionComponentProps<"nav">>;
export const MotionHeader = motion.header as React.FC<
  MotionComponentProps<"header">
>;
export const MotionFooter = motion.footer as React.FC<
  MotionComponentProps<"footer">
>;
export const MotionButton = motion.button as React.FC<
  MotionComponentProps<"button">
>;
export const MotionUL = motion.ul as React.FC<MotionComponentProps<"ul">>;
export const MotionLI = motion.li as React.FC<MotionComponentProps<"li">>;
export const MotionSpan = motion.span as React.FC<MotionComponentProps<"span">>;
export const MotionP = motion.p as React.FC<MotionComponentProps<"p">>;
