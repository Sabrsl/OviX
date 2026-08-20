"""
Unit tests for the Stats module.

Tests for StatsRepository, StatsService, and API endpoints.
"""

import unittest
import tempfile
import os
from pathlib import Path
import sqlite3

from backend.stats.repository import StatsRepository
from backend.stats.service import StatsService
from backend.stats.schemas import (
    ArticleStats,
    AnalysisStats,
    PublicationStats,
    DatabaseStats,
    SystemStats
)


class TestStatsRepository(unittest.TestCase):
    """Test StatsRepository database access layer."""

    def setUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create test database schema
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute("""
            CREATE TABLE analysis_results (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                article_title TEXT NOT NULL,
                page_id INTEGER,
                revision_id INTEGER,
                status TEXT NOT NULL,
                mode TEXT NOT NULL,
                changes_count INTEGER,
                summary TEXT,
                original_content TEXT,
                corrected_content TEXT,
                character_count INTEGER,
                total_links INTEGER,
                dead_links_count INTEGER,
                corrected_links_count INTEGER,
                human_verified INTEGER DEFAULT 0,
                analysis_date TIMESTAMP NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE articles (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                page_id INTEGER,
                revision_id INTEGER,
                status TEXT,
                created_at TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE issues (
                id TEXT PRIMARY KEY,
                article_title TEXT NOT NULL,
                issue_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                suggested_text TEXT,
                created_at TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE actions (
                id TEXT PRIMARY KEY,
                article_title TEXT NOT NULL,
                action_type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP
            )
        """)
        
        # Insert test data
        cursor.execute("""
            INSERT INTO analysis_results 
            (id, job_id, article_title, page_id, revision_id, status, mode, changes_count, 
             character_count, total_links, dead_links_count, corrected_links_count, analysis_date)
            VALUES 
            ('test1', 'job1', 'Article1', 1, 100, 'published', 'IA', 5, 1000, 50, 10, 5, '2024-01-01'),
            ('test2', 'job1', 'Article2', 2, 200, 'pending', 'IA', 3, 800, 40, 8, 4, '2024-01-02'),
            ('test3', 'job2', 'Article3', 3, 300, 'error', 'IA', 0, 600, 30, 0, 0, '2024-01-03'),
            ('test4', 'job2', 'Article4', 4, 400, 'ignored', 'IA', 2, 1200, 60, 12, 6, '2024-01-04')
        """)
        
        cursor.execute("""
            INSERT INTO articles (id, title, page_id, revision_id, status, created_at)
            VALUES ('art1', 'Article1', 1, 100, 'analyzed', '2024-01-01'),
                   ('art2', 'Article2', 2, 200, 'pending', '2024-01-02')
        """)
        
        cursor.execute("""
            INSERT INTO issues (id, article_title, issue_type, severity, suggested_text, created_at)
            VALUES ('iss1', 'Article1', 'dead_link', 'high', 'https://example.com', '2024-01-01'),
                   ('iss2', 'Article1', 'dead_link', 'medium', 'https://example2.com', '2024-01-01'),
                   ('iss3', 'Article2', 'dead_link', 'low', 'https://example3.com', '2024-01-02')
        """)
        
        cursor.execute("""
            INSERT INTO actions (id, article_title, action_type, status, created_at)
            VALUES ('act1', 'Article1', 'publish', 'completed', '2024-01-01'),
                   ('act2', 'Article2', 'analyze', 'completed', '2024-01-02')
        """)
        
        conn.commit()
        conn.close()
        
        self.repository = StatsRepository(self.db_path)

    def tearDown(self):
        """Clean up test database."""
        os.unlink(self.db_path)

    def test_get_article_stats(self):
        """Test article statistics retrieval."""
        stats = self.repository.get_article_stats()
        
        self.assertEqual(stats['total'], 4)
        self.assertEqual(stats['published'], 1)
        self.assertEqual(stats['pending'], 1)
        self.assertEqual(stats['error'], 1)
        self.assertEqual(stats['ignored'], 1)

    def test_get_analysis_stats(self):
        """Test analysis statistics retrieval."""
        stats = self.repository.get_analysis_stats()
        
        self.assertEqual(stats['total'], 4)
        self.assertEqual(stats['successful'], 2)  # published + ignored
        self.assertEqual(stats['failed'], 1)  # error
        self.assertEqual(stats['dead_links_detected'], 30)  # 10 + 8 + 0 + 12
        self.assertEqual(stats['dead_links_corrected'], 15)  # 5 + 4 + 0 + 6
        self.assertEqual(stats['total_links'], 180)  # 50 + 40 + 30 + 60

    def test_get_publication_stats(self):
        """Test publication statistics retrieval."""
        stats = self.repository.get_publication_stats()
        
        self.assertEqual(stats['total'], 1)
        self.assertGreater(stats['publication_rate'], 0)

    def test_get_database_stats(self):
        """Test database statistics retrieval."""
        stats = self.repository.get_database_stats()
        
        self.assertEqual(stats['articles_total'], 2)
        self.assertEqual(stats['issues_total'], 3)
        self.assertEqual(stats['actions_total'], 2)
        self.assertEqual(stats['articles_with_changes'], 3)  # All except error

    def test_get_issues_by_severity(self):
        """Test issues by severity retrieval."""
        stats = self.repository.get_issues_by_severity()
        
        self.assertEqual(stats['high'], 1)
        self.assertEqual(stats['medium'], 1)
        self.assertEqual(stats['low'], 1)


class TestStatsService(unittest.TestCase):
    """Test StatsService business logic layer."""

    def setUp(self):
        """Set up test database and service."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create test database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE analysis_results (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                article_title TEXT NOT NULL,
                page_id INTEGER,
                revision_id INTEGER,
                status TEXT NOT NULL,
                mode TEXT NOT NULL,
                changes_count INTEGER,
                summary TEXT,
                original_content TEXT,
                corrected_content TEXT,
                character_count INTEGER,
                total_links INTEGER,
                dead_links_count INTEGER,
                corrected_links_count INTEGER,
                human_verified INTEGER DEFAULT 0,
                analysis_date TIMESTAMP NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE articles (id TEXT PRIMARY KEY, title TEXT NOT NULL)
        """)
        
        cursor.execute("""
            CREATE TABLE issues (id TEXT PRIMARY KEY, article_title TEXT NOT NULL, severity TEXT NOT NULL)
        """)
        
        cursor.execute("""
            CREATE TABLE actions (id TEXT PRIMARY KEY, article_title TEXT NOT NULL)
        """)
        
        # Insert test data
        cursor.execute("""
            INSERT INTO analysis_results 
            (id, job_id, article_title, page_id, revision_id, status, mode, changes_count, 
             character_count, total_links, dead_links_count, corrected_links_count, analysis_date)
            VALUES 
            ('test1', 'job1', 'Article1', 1, 100, 'published', 'IA', 5, 1000, 50, 10, 5, '2024-01-01'),
            ('test2', 'job1', 'Article2', 2, 200, 'pending', 'IA', 3, 800, 40, 8, 4, '2024-01-02')
        """)
        
        conn.commit()
        conn.close()
        
        self.service = StatsService(self.db_path)

    def tearDown(self):
        """Clean up test database."""
        os.unlink(self.db_path)

    def test_get_article_stats(self):
        """Test article statistics through service."""
        stats = self.service.get_article_stats()
        
        self.assertIsInstance(stats, ArticleStats)
        self.assertEqual(stats.total, 2)
        self.assertEqual(stats.published, 1)
        self.assertEqual(stats.pending, 1)

    def test_get_analysis_stats(self):
        """Test analysis statistics through service."""
        stats = self.service.get_analysis_stats()
        
        self.assertIsInstance(stats, AnalysisStats)
        self.assertEqual(stats.total, 2)
        self.assertEqual(stats.dead_links_detected, 18)
        self.assertEqual(stats.dead_links_corrected, 9)

    def test_get_system_stats(self):
        """Test complete system statistics."""
        stats = self.service.get_system_stats()
        
        self.assertIsInstance(stats, SystemStats)
        self.assertIsInstance(stats.articles, ArticleStats)
        self.assertIsInstance(stats.analysis, AnalysisStats)
        self.assertIsInstance(stats.publication, PublicationStats)
        self.assertIsInstance(stats.database, DatabaseStats)

    def test_get_stats_response(self):
        """Test stats response format."""
        response = self.service.get_stats_response()
        
        self.assertTrue(response.success)
        self.assertEqual(response.source, "database")
        self.assertIsInstance(response.stats, SystemStats)

    def test_get_legacy_format(self):
        """Test legacy format conversion."""
        legacy = self.service.get_legacy_format()
        
        self.assertIn('analyzed_total', legacy)
        self.assertIn('analyzed_published', legacy)
        self.assertIn('dead_links_detected', legacy)
        self.assertEqual(legacy['analyzed_total'], 2)
        self.assertEqual(legacy['analyzed_published'], 1)


class TestStatsSchemas(unittest.TestCase):
    """Test stats schema validation."""

    def test_article_stats_schema(self):
        """Test ArticleStats schema."""
        stats = ArticleStats(total=10, published=5, pending=3)
        self.assertEqual(stats.total, 10)
        self.assertEqual(stats.published, 5)
        self.assertEqual(stats.pending, 3)
        self.assertEqual(stats.rejected, 0)  # Default value

    def test_analysis_stats_schema(self):
        """Test AnalysisStats schema."""
        stats = AnalysisStats(total=100, dead_links_detected=20)
        self.assertEqual(stats.total, 100)
        self.assertEqual(stats.dead_links_detected, 20)
        self.assertEqual(stats.successful, 0)  # Default value

    def test_system_stats_schema(self):
        """Test SystemStats schema."""
        system = SystemStats(
            articles=ArticleStats(total=10),
            analysis=AnalysisStats(total=100)
        )
        self.assertEqual(system.articles.total, 10)
        self.assertEqual(system.analysis.total, 100)


if __name__ == '__main__':
    unittest.main()
