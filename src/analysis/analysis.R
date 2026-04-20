# FIG Valuation Multiple Predictor — Visualizations
# Run after: python3 analysis/regression.py

library(tidyverse)
library(corrplot)

deals       <- read_csv("deals.csv",        show_col_types = FALSE)
coefs       <- read_csv("coefficients.csv", show_col_types = FALSE)
residuals   <- read_csv("residuals.csv",    show_col_types = FALSE)
holdout     <- tryCatch(read_csv("holdout.csv", show_col_types = FALSE), error = function(e) NULL)

MACRO_VARS <- c("T10Y2Y", "UMCSENT", "DSPI_yoy", "CPROFIT_yoy", "COMPUTSA_yoy")

df <- deals |>
  filter(price_to_book > 0, price_to_book < 5) |>
  mutate(signal_date = as.Date(signal_date), year = year(signal_date))

cat("Deals:", nrow(df), "\n")
cat("Date range:", format(min(df$signal_date)), "to", format(max(df$signal_date)), "\n\n")


# ── 1. P/B distribution ──────────────────────────────────────────────────────

ggplot(df, aes(x = price_to_book)) +
  geom_histogram(bins = 40, fill = "#2c5f8a", color = "white", linewidth = 0.2) +
  geom_vline(xintercept = median(df$price_to_book, na.rm = TRUE),
             linetype = "dashed", color = "firebrick") +
  labs(title = "Distribution of acquisition P/B multiples",
       subtitle = paste0("n = ", nrow(df), " bank deals, 1990–present"),
       x = "Price-to-book multiple", y = "Count") +
  theme_minimal()

ggsave("plots/ptb_distribution.png", width = 7, height = 4, dpi = 150)


# ── 2. P/B over time ─────────────────────────────────────────────────────────

ggplot(df, aes(x = signal_date, y = price_to_book)) +
  geom_point(alpha = 0.35, size = 1.2, color = "#2c5f8a") +
  geom_smooth(method = "loess", span = 0.3, color = "firebrick", se = TRUE) +
  labs(title = "Bank acquisition P/B multiples over time",
       subtitle = "Loess trend — each point is one deal",
       x = NULL, y = "Price-to-book") +
  theme_minimal()

ggsave("plots/ptb_over_time.png", width = 9, height = 4, dpi = 150)


# ── 3. Deals per year ────────────────────────────────────────────────────────

df |>
  count(year) |>
  ggplot(aes(x = year, y = n)) +
  geom_col(fill = "#2c5f8a") +
  labs(title = "Bank acquisitions per year in dataset",
       x = NULL, y = "Deals with recoverable price") +
  theme_minimal()

ggsave("plots/deals_per_year.png", width = 9, height = 4, dpi = 150)


# ── 4. Correlation matrix ────────────────────────────────────────────────────

cor_matrix <- df |>
  select(price_to_book, all_of(MACRO_VARS)) |>
  drop_na() |>
  cor(use = "complete.obs")

png("plots/correlation_matrix.png", width = 700, height = 600)
corrplot(cor_matrix,
         method = "color", type = "upper", order = "hclust",
         addCoef.col = "black", number.cex = 0.75,
         tl.col = "black", tl.srt = 45,
         col = colorRampPalette(c("#d73027", "white", "#4575b4"))(200),
         title = "Correlation matrix — macro signals + P/B",
         mar = c(0, 0, 2, 0))
dev.off()


# ── 5. Coefficient plot ──────────────────────────────────────────────────────

coefs |>
  filter(term != "(Intercept)") |>
  ggplot(aes(x = estimate, y = reorder(term, estimate))) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "gray50") +
  geom_errorbarh(aes(xmin = conf_low, xmax = conf_high),
                 height = 0.2, color = "#2c5f8a") +
  geom_point(size = 3, color = "#2c5f8a") +
  labs(title = "OLS coefficient estimates (95% CI)",
       subtitle = "Outcome: price-to-book multiple at acquisition",
       x = "Coefficient", y = NULL) +
  theme_minimal()

ggsave("plots/coefficients.png", width = 7, height = 4, dpi = 150)


# ── 6. Regression diagnostics ────────────────────────────────────────────────

p1 <- ggplot(residuals, aes(x = fitted, y = residual)) +
  geom_point(alpha = 0.4, color = "#2c5f8a") +
  geom_hline(yintercept = 0, linetype = "dashed") +
  geom_smooth(method = "loess", se = FALSE, color = "firebrick") +
  labs(title = "Residuals vs Fitted", x = "Fitted values", y = "Residuals") +
  theme_minimal()

p2 <- ggplot(residuals, aes(sample = residual)) +
  stat_qq(alpha = 0.4, color = "#2c5f8a") +
  stat_qq_line(color = "firebrick") +
  labs(title = "Normal Q-Q", x = "Theoretical quantiles", y = "Sample quantiles") +
  theme_minimal()

p3 <- ggplot(residuals, aes(x = fitted, y = sqrt(abs(residual)))) +
  geom_point(alpha = 0.4, color = "#2c5f8a") +
  geom_smooth(method = "loess", se = FALSE, color = "firebrick") +
  labs(title = "Scale-Location", x = "Fitted values", y = "√|Residuals|") +
  theme_minimal()

p4 <- ggplot(residuals, aes(x = leverage, y = residual)) +
  geom_point(alpha = 0.4, color = "#2c5f8a") +
  geom_hline(yintercept = 0, linetype = "dashed") +
  geom_smooth(method = "loess", se = FALSE, color = "firebrick") +
  labs(title = "Residuals vs Leverage", x = "Leverage", y = "Residuals") +
  theme_minimal()

library(patchwork)
(p1 | p2) / (p3 | p4)
ggsave("plots/diagnostics.png", width = 10, height = 7, dpi = 150)


# ── 7. Holdout scatter ───────────────────────────────────────────────────────

if (!is.null(holdout)) {
  ggplot(holdout, aes(x = predicted, y = actual)) +
    geom_abline(slope = 1, intercept = 0, linetype = "dashed", color = "gray50") +
    geom_point(alpha = 0.6, color = "#2c5f8a") +
    labs(title = "Predicted vs. actual P/B (holdout 2020+)",
         x = "Predicted P/B", y = "Actual P/B") +
    theme_minimal()

  ggsave("plots/holdout_scatter.png", width = 6, height = 5, dpi = 150)
}

cat("Plots saved to plots/\n")
