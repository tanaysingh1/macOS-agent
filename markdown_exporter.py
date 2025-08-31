import os
from typing import Optional
from mac_element import MacElementNode


class MarkdownExporter:
    """Utility class for exporting UI tree data to various markdown formats"""
    
    @staticmethod
    def export_full_tree_to_file(root_node: MacElementNode, filename: str = "full_ui_tree.md") -> bool:
        """
        Export the complete UI tree to a markdown file showing all elements and their relationships
        
        Args:
            root_node: The root node of the UI tree
            filename: Output filename for the markdown file
            
        Returns:
            bool: True if export was successful, False otherwise
        """
        try:
            markdown_content = MarkdownExporter._generate_full_tree_markdown(root_node)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("# Complete UI Tree Structure\n\n")
                f.write("This document contains the complete UI hierarchy with all elements, their actions, and attributes.\n\n")
                f.write("Format: `{elementRole} actions={actionsList} attributes={attributesList}`\n\n")
                f.write("---\n\n")
                f.write(markdown_content)
            
            print(f"✅ Full UI tree exported to: {filename}")
            return True
            
        except Exception as e:
            print(f"❌ Error exporting full tree: {e}")
            return False
    
    @staticmethod
    def export_interactive_and_context_to_file(root_node: MacElementNode, filename: str = "interactive_elements.md") -> bool:
        """
        Export interactive and context elements to a markdown file
        
        Args:
            root_node: The root node of the UI tree
            filename: Output filename for the markdown file
            
        Returns:
            bool: True if export was successful, False otherwise
        """
        try:
            interactive_content = root_node.export_interactive_elements_markdown()
            
            # Separate interactive and context elements for better organization
            lines = interactive_content.split('\n')
            interactive_lines = [line for line in lines if line and not line.startswith('Text:')]
            context_lines = [line for line in lines if line.startswith('Text:')]
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("# Interactive and Context Elements\n\n")
                f.write("This document contains only the elements that can be interacted with or provide context information.\n\n")
                f.write("## Format\n")
                f.write("- Interactive elements: `{ID}[:] <{role} {attributes}>`\n")
                f.write("- Context elements: `Text: {text_content}`\n\n")
                f.write("## Interactive Elements\n\n")
                f.write("These elements can be clicked, typed into, or otherwise interacted with:\n\n")
                
                if interactive_lines:
                    for line in interactive_lines:
                        if line.strip():
                            f.write(f"{line}\n")
                else:
                    f.write("No interactive elements found.\n")
                
                f.write("\n## Context Elements\n\n")
                f.write("These elements provide readable text and context information:\n\n")
                
                if context_lines:
                    for line in context_lines:
                        if line.strip():
                            f.write(f"{line}\n")
                else:
                    f.write("No context elements found.\n")
            
            print(f"✅ Interactive and context elements exported to: {filename}")
            return True
            
        except Exception as e:
            print(f"❌ Error exporting interactive elements: {e}")
            return False
    
    @staticmethod
    def export_stats_to_file(root_node: MacElementNode, builder_stats: dict, filename: str = "ui_tree_stats.md") -> bool:
        """
        Export statistics about the UI tree to a markdown file
        
        Args:
            root_node: The root node of the UI tree
            builder_stats: Statistics from the tree builder
            filename: Output filename for the markdown file
            
        Returns:
            bool: True if export was successful, False otherwise
        """
        try:
            interactive_elements = root_node.find_interactive_elements()
            context_elements = root_node.find_context_elements()
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("# UI Tree Statistics\n\n")
                f.write("## Builder Statistics\n\n")
                f.write(f"- **Total Interactive Elements**: {builder_stats.get('total_interactive_elements', 0)}\n")
                f.write(f"- **Processed Elements Count**: {builder_stats.get('processed_elements_count', 0)}\n")
                f.write(f"- **Next Highlight Index**: {builder_stats.get('next_highlight_index', 0)}\n")
                f.write(f"- **Application PID**: {builder_stats.get('current_app_pid', 'Unknown')}\n\n")
                
                f.write("## Element Breakdown\n\n")
                f.write(f"- **Interactive Elements Found**: {len(interactive_elements)}\n")
                f.write(f"- **Context Elements Found**: {len(context_elements)}\n\n")
                
                if interactive_elements:
                    f.write("### Interactive Elements by Role\n\n")
                    role_counts = {}
                    for element in interactive_elements:
                        role = element.role
                        role_counts[role] = role_counts.get(role, 0) + 1
                    
                    for role, count in sorted(role_counts.items()):
                        f.write(f"- **{role}**: {count}\n")
                    f.write("\n")
                
                if context_elements:
                    f.write("### Context Elements by Role\n\n")
                    context_role_counts = {}
                    for element in context_elements:
                        role = element.role
                        context_role_counts[role] = context_role_counts.get(role, 0) + 1
                    
                    for role, count in sorted(context_role_counts.items()):
                        f.write(f"- **{role}**: {count}\n")
                    f.write("\n")
            
            print(f"✅ UI tree statistics exported to: {filename}")
            return True
            
        except Exception as e:
            print(f"❌ Error exporting statistics: {e}")
            return False
    
    @staticmethod
    def _generate_full_tree_markdown(node: MacElementNode, depth: int = 0) -> str:
        """Generate markdown content for the full tree structure"""
        return node.export_full_tree_markdown(depth)
    
    @staticmethod
    def export_accessibility_paths_to_file(root_node: MacElementNode, filename: str = "accessibility_paths.md") -> bool:
        """
        Export accessibility paths for all elements to help with debugging and navigation
        
        Args:
            root_node: The root node of the UI tree
            filename: Output filename for the markdown file
            
        Returns:
            bool: True if export was successful, False otherwise
        """
        try:
            interactive_elements = root_node.find_interactive_elements()
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("# Accessibility Paths\n\n")
                f.write("This document shows the accessibility paths for all interactive elements.\n")
                f.write("These paths can be used to locate elements programmatically.\n\n")
                
                f.write("## Interactive Element Paths\n\n")
                
                if interactive_elements:
                    for element in interactive_elements:
                        f.write(f"**Index {element.highlight_index}** ({element.role})\n")
                        f.write(f"- Path: `{element.accessibility_path}`\n")
                        if element.attributes.get('title'):
                            f.write(f"- Title: {element.attributes['title']}\n")
                        if element.actions:
                            f.write(f"- Actions: {element.actions}\n")
                        f.write("\n")
                else:
                    f.write("No interactive elements found.\n")
            
            print(f"✅ Accessibility paths exported to: {filename}")
            return True
            
        except Exception as e:
            print(f"❌ Error exporting accessibility paths: {e}")
            return False