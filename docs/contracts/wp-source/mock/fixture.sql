-- Synthetic wp-source fixture for importer tests. See README.md.
-- Only the tables and columns docs/contracts/wp-source.md reads, plus primary keys.
-- Column names, types and order follow db/dump.sql; no rows come from it.
-- Portable subset: loads in MariaDB 11 and in sqlite3.

DROP TABLE IF EXISTS `wp_terms`;
CREATE TABLE `wp_terms` (
  `term_id` bigint(20) NOT NULL,
  `name` varchar(200) NOT NULL DEFAULT '',
  `slug` varchar(200) NOT NULL DEFAULT '',
  PRIMARY KEY (`term_id`)
);

DROP TABLE IF EXISTS `wp_term_taxonomy`;
CREATE TABLE `wp_term_taxonomy` (
  `term_taxonomy_id` bigint(20) NOT NULL,
  `term_id` bigint(20) NOT NULL DEFAULT 0,
  `taxonomy` varchar(32) NOT NULL DEFAULT '',
  PRIMARY KEY (`term_taxonomy_id`),
  UNIQUE (`term_id`, `taxonomy`)
);

DROP TABLE IF EXISTS `wp_term_relationships`;
CREATE TABLE `wp_term_relationships` (
  `object_id` bigint(20) NOT NULL DEFAULT 0,
  `term_taxonomy_id` bigint(20) NOT NULL DEFAULT 0,
  PRIMARY KEY (`object_id`, `term_taxonomy_id`)
);

DROP TABLE IF EXISTS `wp_posts`;
CREATE TABLE `wp_posts` (
  `ID` bigint(20) NOT NULL,
  `post_author` bigint(20) NOT NULL DEFAULT 0,
  `post_date_gmt` datetime NOT NULL,
  `post_content` longtext NOT NULL,
  `post_title` text NOT NULL,
  `post_status` varchar(20) NOT NULL DEFAULT 'publish',
  `post_name` varchar(200) NOT NULL DEFAULT '',
  `post_type` varchar(20) NOT NULL DEFAULT 'post',
  PRIMARY KEY (`ID`)
);

DROP TABLE IF EXISTS `wp_postmeta`;
CREATE TABLE `wp_postmeta` (
  `meta_id` bigint(20) NOT NULL,
  `post_id` bigint(20) NOT NULL DEFAULT 0,
  `meta_key` varchar(255) DEFAULT NULL,
  `meta_value` longtext DEFAULT NULL,
  PRIMARY KEY (`meta_id`)
);

DROP TABLE IF EXISTS `wp_users`;
CREATE TABLE `wp_users` (
  `ID` bigint(20) NOT NULL,
  `user_login` varchar(60) NOT NULL DEFAULT '',
  `user_pass` varchar(255) NOT NULL DEFAULT '',
  `user_email` varchar(100) NOT NULL DEFAULT '',
  `display_name` varchar(250) NOT NULL DEFAULT '',
  PRIMARY KEY (`ID`)
);

DROP TABLE IF EXISTS `wp_usermeta`;
CREATE TABLE `wp_usermeta` (
  `umeta_id` bigint(20) NOT NULL,
  `user_id` bigint(20) NOT NULL DEFAULT 0,
  `meta_key` varchar(255) DEFAULT NULL,
  `meta_value` longtext DEFAULT NULL,
  PRIMARY KEY (`umeta_id`)
);

-- Industries. Slugs deliberately differ from the slugified names.
-- term_taxonomy_id differs from term_id so a wrong join shows up.
INSERT INTO `wp_terms` (`term_id`, `name`, `slug`) VALUES
  (1, 'Mock Insurance', 'ins-mock'),
  (2, 'Mock Banking', 'bank-mock');
INSERT INTO `wp_term_taxonomy` (`term_taxonomy_id`, `term_id`, `taxonomy`) VALUES
  (11, 1, 'industry'),
  (12, 2, 'industry');

-- Brands: 101 A (publish), 102 B (publish), 103 D (draft, never imported).
-- Reviews: 201 R1 (valid), 202 R2 (brand 9999 missing), 203 R3 (rating 7).
INSERT INTO `wp_posts` (`ID`, `post_author`, `post_date_gmt`, `post_content`, `post_title`, `post_status`, `post_name`, `post_type`) VALUES
  (101, 1, '2026-01-10 09:00:00', '<p>Alpha Mock Co. is a <strong>synthetic</strong> insurer.</p><p>Second paragraph, not in the short description.</p>', 'Alpha Mock Co.', 'publish', 'alpha-mock', 'brand'),
  (102, 1, '2026-01-11 09:00:00', '<p>Beta &amp; Sons is a synthetic bank.</p>', 'Beta & Sons', 'publish', 'beta-and-sons', 'brand'),
  (103, 1, '2026-01-12 09:00:00', '<p>Draft brand.</p>', 'Delta Draft', 'draft', 'delta-draft', 'brand'),
  (201, 2, '2026-02-01 12:30:00', '<p>Claim paid in a week.</p>', 'Quick claim', 'publish', 'quick-claim', 'review'),
  (202, 2, '2026-02-02 12:30:00', '<p>Brand no longer exists.</p>', 'Orphan review', 'publish', 'orphan-review', 'review'),
  (203, 2, '2026-02-03 12:30:00', '<p>Rating out of range.</p>', 'Seven stars', 'publish', 'seven-stars', 'review');

INSERT INTO `wp_term_relationships` (`object_id`, `term_taxonomy_id`) VALUES
  (101, 11),
  (102, 12),
  (103, 11);

-- Keys starting with `_` (other than the two Yoast keys) are ACF twins and must not be read.
INSERT INTO `wp_postmeta` (`meta_id`, `post_id`, `meta_key`, `meta_value`) VALUES
  (1, 101, 'website_url', 'https://alpha-mock.example.com'),
  (2, 101, '_website_url', 'field_mock_website_url'),
  (3, 101, 'founded_year', '1990'),
  (4, 101, 'headquarters', 'Springfield, ZZ'),
  (5, 101, 'average_rating', '4.5'),
  (6, 101, '_yoast_wpseo_title', 'Alpha Mock Co. Reviews'),
  (7, 101, '_yoast_wpseo_metadesc', 'Synthetic reviews of Alpha Mock Co.'),
  (8, 102, 'website_url', ''),
  (9, 102, 'founded_year', ''),
  (10, 102, 'headquarters', 'Shelbyville, ZZ'),
  (11, 102, 'average_rating', ''),
  (12, 103, 'website_url', 'https://delta-draft.example.com'),
  (13, 201, 'rating', '4'),
  (14, 201, '_rating', 'field_mock_rating'),
  (15, 201, 'reviewer_name', 'Mock Reader'),
  (16, 201, 'reviewer_location', 'Springfield, ZZ'),
  (17, 201, 'brand', '101'),
  (18, 202, 'rating', '3'),
  (19, 202, 'reviewer_name', 'Mock Reader'),
  (20, 202, 'reviewer_location', 'Springfield, ZZ'),
  (21, 202, 'brand', '9999'),
  (22, 203, 'rating', '7'),
  (23, 203, 'reviewer_name', 'Mock Reader'),
  (24, 203, 'reviewer_location', 'Springfield, ZZ'),
  (25, 203, 'brand', '101');

-- Hashes from make_hashes.py; passwords are in README.md.
INSERT INTO `wp_users` (`ID`, `user_login`, `user_pass`, `user_email`, `display_name`) VALUES
  (1, 'mock_admin', '$wp$2y$10$hWO9u1uK95BYiGHuCUu.a.wQtTcSaQya4gsjuSW.VhWH4ibTyKUQ.', 'mock_admin@example.com', 'Mock Admin'),
  (2, 'mock_reader', '$wp$2y$10$DRYJXXP0nbCRgGWKjxvP/OLK.m4V4jgyNLgY5mX3X0DKG5nXFfUJu', 'mock_reader@example.com', 'Mock Reader');

INSERT INTO `wp_usermeta` (`umeta_id`, `user_id`, `meta_key`, `meta_value`) VALUES
  (1, 1, 'wp_capabilities', 'a:1:{s:13:"administrator";b:1;}'),
  (2, 2, 'wp_capabilities', 'a:1:{s:10:"subscriber";b:1;}');
