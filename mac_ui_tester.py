import asyncio
import logging
import os
from typing import Optional, Dict, Any

import Cocoa
from ApplicationServices import AXUIElementPerformAction, kAXPressAction

from mac_element import MacElementNode
from mac_tree_builder import MacUITreeBuilder
from markdown_exporter import MarkdownExporter

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MacUITester:
    """Tester class for the macOS UI tree system using Finder as a test application"""
    
    def __init__(self):
        self.builder = MacUITreeBuilder()
        self.finder_pid: Optional[int] = None
        self.root_node: Optional[MacElementNode] = None
        
    async def find_finder_application(self) -> Optional[int]:
        """Find and return the PID of the Finder application"""
        try:
            workspace = Cocoa.NSWorkspace.sharedWorkspace()
            
            # Look for Finder in running applications
            for app in workspace.runningApplications():
                bundle_id = app.bundleIdentifier()
                if bundle_id and 'finder' in bundle_id.lower():
                    pid = app.processIdentifier()
                    app_name = app.localizedName()
                    logger.info(f"Found Finder application: {app_name} (PID: {pid}, Bundle: {bundle_id})")
                    return pid
            
            # If Finder is not found, try to launch it
            logger.info("Finder not found in running applications, attempting to launch...")
            success = workspace.launchApplication_("Finder")
            if success:
                # Wait a moment for Finder to launch
                await asyncio.sleep(2)
                # Try to find it again
                for app in workspace.runningApplications():
                    bundle_id = app.bundleIdentifier()
                    if bundle_id and 'finder' in bundle_id.lower():
                        pid = app.processIdentifier()
                        logger.info(f"Successfully launched Finder (PID: {pid})")
                        return pid
            
            logger.error("Could not find or launch Finder application")
            return None
            
        except Exception as e:
            logger.error(f"Error finding Finder application: {e}")
            return None
    
    async def test_finder_tree(self) -> bool:
        """Test building a UI tree for the Finder application"""
        try:
            logger.info("=== Starting Finder UI Tree Test ===")
            
            # Find Finder application
            self.finder_pid = await self.find_finder_application()
            if not self.finder_pid:
                logger.error("Failed to find Finder application")
                return False
            
            logger.info(f"Building UI tree for Finder (PID: {self.finder_pid})...")
            
            # Build the UI tree
            self.root_node = await self.builder.build_tree(self.finder_pid)
            
            if not self.root_node:
                logger.error("Failed to build UI tree")
                return False
            
            logger.info("✅ Successfully built UI tree for Finder")
            
            # Get some basic statistics
            stats = self.builder.get_stats()
            interactive_elements = self.root_node.find_interactive_elements()
            context_elements = self.root_node.find_context_elements()
            
            logger.info(f"Tree Statistics:")
            logger.info(f"  - Interactive elements: {len(interactive_elements)}")
            logger.info(f"  - Context elements: {len(context_elements)}")
            logger.info(f"  - Total processed elements: {stats['processed_elements_count']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error during Finder tree test: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def export_finder_markdown(self) -> bool:
        """Export Finder UI tree data to markdown files"""
        try:
            if not self.root_node:
                logger.error("No UI tree available. Run test_finder_tree() first.")
                return False
            
            logger.info("=== Exporting Finder UI Tree to Markdown ===")
            
            # Get current directory for output files
            output_dir = os.getcwd()
            
            # Export full tree
            full_tree_file = os.path.join(output_dir, "full_ui_tree.md")
            success1 = MarkdownExporter.export_full_tree_to_file(self.root_node, full_tree_file)
            
            # Export interactive and context elements
            interactive_file = os.path.join(output_dir, "interactive_elements.md")
            success2 = MarkdownExporter.export_interactive_and_context_to_file(self.root_node, interactive_file)
            
            # Export statistics
            stats_file = os.path.join(output_dir, "ui_tree_stats.md")
            builder_stats = self.builder.get_stats()
            success3 = MarkdownExporter.export_stats_to_file(self.root_node, builder_stats, stats_file)
            
            # Export accessibility paths
            paths_file = os.path.join(output_dir, "accessibility_paths.md")
            success4 = MarkdownExporter.export_accessibility_paths_to_file(self.root_node, paths_file)
            
            if all([success1, success2, success3, success4]):
                logger.info("✅ All markdown files exported successfully:")
                logger.info(f"  - Full UI Tree: {full_tree_file}")
                logger.info(f"  - Interactive Elements: {interactive_file}")
                logger.info(f"  - Statistics: {stats_file}")
                logger.info(f"  - Accessibility Paths: {paths_file}")
                return True
            else:
                logger.error("❌ Some exports failed")
                return False
                
        except Exception as e:
            logger.error(f"Error exporting markdown files: {e}")
            return False
    
    def verify_element_traceability(self) -> bool:
        """Verify that interactive elements can be traced back to their AX element references"""
        try:
            if not self.root_node:
                logger.error("No UI tree available. Run test_finder_tree() first.")
                return False
            
            logger.info("=== Verifying Element Traceability ===")
            
            interactive_elements = self.builder.get_all_interactive_elements()
            
            if not interactive_elements:
                logger.warning("No interactive elements found to verify")
                return True
            
            verified_count = 0
            total_count = len(interactive_elements)
            
            for index, element in interactive_elements.items():
                try:
                    # Verify the element has an AX reference
                    if element._element is None:
                        logger.warning(f"Element {index} ({element.role}) has no AX element reference")
                        continue
                    
                    # Verify we can retrieve the element by index
                    retrieved_element = self.builder.get_element_by_index(index)
                    if retrieved_element is None:
                        logger.warning(f"Could not retrieve element by index {index}")
                        continue
                    
                    # Verify the retrieved element matches
                    if retrieved_element != element:
                        logger.warning(f"Retrieved element doesn't match original for index {index}")
                        continue
                    
                    # Verify the element has actions (if it's truly interactive)
                    if not element.actions:
                        logger.debug(f"Element {index} ({element.role}) has no actions but is marked interactive")
                    
                    verified_count += 1
                    logger.debug(f"✅ Element {index} ({element.role}) verified successfully")
                    
                except Exception as e:
                    logger.warning(f"Error verifying element {index}: {e}")
                    continue
            
            success_rate = (verified_count / total_count) * 100 if total_count > 0 else 0
            logger.info(f"Element Traceability Results:")
            logger.info(f"  - Total interactive elements: {total_count}")
            logger.info(f"  - Successfully verified: {verified_count}")
            logger.info(f"  - Success rate: {success_rate:.1f}%")
            
            return verified_count == total_count
            
        except Exception as e:
            logger.error(f"Error verifying element traceability: {e}")
            return False
    
    def test_element_action_simulation(self) -> bool:
        """Test that we can simulate actions on elements (without actually performing them)"""
        try:
            if not self.root_node:
                logger.error("No UI tree available. Run test_finder_tree() first.")
                return False
            
            logger.info("=== Testing Element Action Simulation ===")
            
            interactive_elements = self.builder.get_all_interactive_elements()
            
            if not interactive_elements:
                logger.warning("No interactive elements found to test")
                return True
            
            # Test a few elements to see if we can access their AX references
            test_count = min(5, len(interactive_elements))  # Test up to 5 elements
            tested = 0
            successful = 0
            
            for index, element in list(interactive_elements.items())[:test_count]:
                try:
                    tested += 1
                    
                    if element._element is None:
                        logger.warning(f"Element {index} has no AX reference")
                        continue
                    
                    # Check if element supports AXPress action (most common)
                    if 'AXPress' in element.actions:
                        logger.info(f"Element {index} ({element.role}) supports AXPress - could simulate click")
                        successful += 1
                    elif element.actions:
                        logger.info(f"Element {index} ({element.role}) supports actions: {element.actions}")
                        successful += 1
                    else:
                        logger.debug(f"Element {index} ({element.role}) has no testable actions")
                
                except Exception as e:
                    logger.warning(f"Error testing element {index}: {e}")
                    continue
            
            logger.info(f"Action Simulation Test Results:")
            logger.info(f"  - Elements tested: {tested}")
            logger.info(f"  - Elements with actionable references: {successful}")
            
            return successful > 0
            
        except Exception as e:
            logger.error(f"Error testing element actions: {e}")
            return False
    
    async def run_complete_test(self) -> bool:
        """Run the complete test suite"""
        try:
            logger.info("🚀 Starting Complete MacUI Tester Suite")
            
            # Step 1: Build tree
            step1_success = await self.test_finder_tree()
            if not step1_success:
                logger.error("❌ Step 1 (Build Tree) failed")
                return False
            
            # Step 2: Export markdown
            step2_success = await self.export_finder_markdown()
            if not step2_success:
                logger.error("❌ Step 2 (Export Markdown) failed")
                return False
            
            # Step 3: Verify traceability
            step3_success = self.verify_element_traceability()
            if not step3_success:
                logger.warning("⚠️ Step 3 (Verify Traceability) had issues")
            
            # Step 4: Test action simulation
            step4_success = self.test_element_action_simulation()
            if not step4_success:
                logger.warning("⚠️ Step 4 (Test Actions) had issues")
            
            # Final result
            overall_success = step1_success and step2_success
            
            if overall_success:
                logger.info("🎉 Complete test suite finished successfully!")
                logger.info("Check the generated markdown files to see the UI tree data.")
            else:
                logger.error("❌ Test suite completed with errors")
            
            return overall_success
            
        except Exception as e:
            logger.error(f"Error during complete test: {e}")
            return False
        finally:
            # Cleanup
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        try:
            if self.builder:
                self.builder.cleanup()
            logger.info("🧹 Cleanup completed")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")


async def main():
    """Main function to run the tester"""
    tester = MacUITester()
    
    try:
        success = await tester.run_complete_test()
        if success:
            print("\n✅ All tests completed successfully!")
            print("📄 Check the generated markdown files:")
            print("  - full_ui_tree.md")
            print("  - interactive_elements.md") 
            print("  - ui_tree_stats.md")
            print("  - accessibility_paths.md")
        else:
            print("\n❌ Tests completed with some failures.")
    
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())