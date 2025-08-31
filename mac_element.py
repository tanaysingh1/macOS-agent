from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from functools import cached_property


@dataclass
class MacElementNode:
    """Represents a UI element in macOS with enhanced accessibility information"""
    # Required fields
    role: str
    identifier: str
    attributes: Dict[str, Any]
    is_visible: bool
    app_pid: int

    # Optional fields
    children: List['MacElementNode'] = field(default_factory=list)
    parent: Optional['MacElementNode'] = None
    is_interactive: bool = False
    highlight_index: Optional[int] = None
    _element = None  # Store AX element reference for action execution

    @property
    def actions(self) -> List[str]:
        """Get the list of available actions for this element"""
        return self.attributes.get('actions', [])

    @property
    def enabled(self) -> bool:
        """Check if the element is enabled"""
        return self.attributes.get('enabled', True)

    @property
    def position(self) -> Optional[tuple]:
        """Get the element's position"""
        return self.attributes.get('position')

    @property
    def size(self) -> Optional[tuple]:
        """Get the element's size"""
        return self.attributes.get('size')

    def __repr__(self) -> str:
        """Enhanced string representation including more attributes"""
        role_str = f'<{self.role}'
        
        # Add important attributes to the string representation
        important_attrs = ['title', 'value', 'description', 'enabled']
        for key in important_attrs:
            if key in self.attributes:
                role_str += f' {key}="{self.attributes[key]}"'

        # Add position and size if available
        if self.position:
            role_str += f' pos={self.position}'
        if self.size:
            role_str += f' size={self.size}'
        
        role_str += '>'

        # Add status indicators
        extras = []
        if self.is_interactive:
            extras.append('interactive')
            if self.actions:
                extras.append(f'actions={self.actions}')
        if self.highlight_index is not None:
            extras.append(f'highlight:{self.highlight_index}')
        if not self.enabled:
            extras.append('disabled')
            
        if extras:
            role_str += f' [{", ".join(extras)}]'
        
        return role_str

    def export_full_tree_markdown(self, depth: int = 0) -> str:
        """Export the complete UI tree as markdown with all elements and their attributes"""
        formatted_text = []
        indent = "  " * depth
        
        # Build attributes string for this element
        attrs_list = []
        if self.actions:
            attrs_list.append(f"actions={self.actions}")
        
        # Add other important attributes
        for key, value in self.attributes.items():
            if key != 'actions':  # actions already handled above
                attrs_list.append(f"{key}={repr(value)}")
        
        attrs_str = " " + " ".join(attrs_list) if attrs_list else ""
        
        # Format this element
        formatted_text.append(f"{indent}{self.role}{attrs_str}")
        
        # Recursively format children
        for child in self.children:
            formatted_text.append(child.export_full_tree_markdown(depth + 1))
        
        return "\n".join(formatted_text)

    def export_interactive_elements_markdown(self) -> str:
        """Export interactive elements grouped by role and actions, plus context elements"""
        from collections import defaultdict
        
        # Group interactive elements by role and actions
        interactive_groups = defaultdict(list)
        context_elements = []

        def process_node(node: 'MacElementNode') -> None:
            # Collect interactive elements with numerical IDs
            if node.highlight_index is not None:
                actions_str = ",".join(sorted(node.actions)) if node.actions else ""
                group_key = f"{node.role}|{actions_str}"
                
                # Build attributes string (excluding 'enabled' and 'actions')
                attrs_parts = []
                important_attrs = ['title', 'value', 'description']
                for key in important_attrs:
                    if key in node.attributes and node.attributes[key] is not None:
                        attrs_parts.append(f'{key}="{node.attributes[key]}"')
                
                attrs_str = " " + " ".join(attrs_parts) if attrs_parts else ""
                interactive_groups[group_key].append((node.highlight_index, attrs_str))
            
            # Collect context elements (non-interactive AXStaticText or read-only AXTextField)
            elif (node.role in ['AXStaticText', 'AXTextField'] and 
                  not node.is_interactive):
                # Only include context elements that have meaningful text content
                text_content = (
                    node.attributes.get('value') or 
                    node.attributes.get('title') or 
                    node.attributes.get('description')
                )
                if text_content:
                    context_elements.append(text_content)

            # Recursively process children
            for child in node.children:
                process_node(child)

        process_node(self)
        
        # Format the grouped output
        formatted_text = []
        
        # Sort groups by role name for consistent output
        for group_key in sorted(interactive_groups.keys()):
            role, actions_str = group_key.split('|', 1)
            elements = interactive_groups[group_key]
            
            # Separate elements with properties from those without
            elements_with_props = []
            elements_without_props = []
            
            for index, attrs_str in elements:
                if attrs_str.strip():  # Has attributes beyond just actions and role
                    elements_with_props.append((index, attrs_str))
                else:  # No meaningful attributes
                    elements_without_props.append(index)
            
            # Create the group header with markdown formatting
            if actions_str:
                group_header = f'## **{role}s** with actions `{actions_str}`'
            else:
                group_header = f'## **{role}s** with no actions'
            
            # Only add this group if there are elements to show
            if elements_with_props or elements_without_props:
                formatted_text.append(group_header)
                formatted_text.append("")  # Empty line for spacing
                
                # Add elements with properties (one per line)
                for index, attrs_str in elements_with_props:
                    formatted_text.append(f'- **{index}[:]**{attrs_str}')
                
                # Add summary for elements without properties
                if elements_without_props:
                    count = len(elements_without_props)
                    if count == 1:
                        formatted_text.append(f'- *1 unnamed element* (ID: {elements_without_props[0]})')
                    else:
                        ids_str = ', '.join(map(str, elements_without_props))
                        formatted_text.append(f'- *{count} unnamed elements* (IDs: {ids_str})')
                
                formatted_text.append("")  # Empty line between groups
        
        # Add context elements with markdown formatting
        if context_elements:
            formatted_text.append("## **Context Text Elements**")
            formatted_text.append("")
            for text in context_elements:
                formatted_text.append(f'- *{text}*')
        
        return '\n'.join(formatted_text)

    def get_clickable_elements_string(self) -> str:
        """Compatibility method that matches the original implementation"""
        return self.export_interactive_elements_markdown()

    def get_detailed_info(self) -> str:
        """Return a detailed string with all attributes of the element"""
        details = [
            f"Role: {self.role}",
            f"Identifier: {self.identifier}",
            f"Interactive: {self.is_interactive}",
            f"Enabled: {self.enabled}",
            f"Visible: {self.is_visible}"
        ]
        
        if self.actions:
            details.append(f"Actions: {self.actions}")
        
        if self.position:
            details.append(f"Position: {self.position}")
        
        if self.size:
            details.append(f"Size: {self.size}")

        for key, value in self.attributes.items():
            if key not in ['actions', 'enabled', 'position', 'size']:
                details.append(f"{key}: {value}")
                
        return ", ".join(details)

    def get_detailed_string(self, indent: int = 0) -> str:
        """Recursively build a detailed string representation of the UI tree"""
        spaces = " " * indent
        result = f"{spaces}{self.__repr__()}\n{spaces}Details: {self.get_detailed_info()}"
        for child in self.children:
            result += "\n" + child.get_detailed_string(indent + 2)
        return result

    @cached_property
    def accessibility_path(self) -> str:
        """Generate a unique path to this element including more identifiers"""
        path_components = []
        current = self
        while current.parent is not None:
            role = current.role
            
            # Add identifiers to make the path more specific
            identifiers = []
            if 'title' in current.attributes:
                identifiers.append(f"title={current.attributes['title']}")
            if 'description' in current.attributes:
                identifiers.append(f"desc={current.attributes['description']}")
                
            # Count siblings with same role
            siblings = [s for s in current.parent.children if s.role == role]
            if len(siblings) > 1:
                idx = siblings.index(current) + 1
                path_component = f"{role}[{idx}]"
            else:
                path_component = role
                
            # Add identifiers if available
            if identifiers:
                path_component += f"({','.join(identifiers)})"
                
            path_components.append(path_component)
            current = current.parent
            
        path_components.reverse()
        return '/' + '/'.join(path_components)

    def find_element_by_path(self, path: str) -> Optional['MacElementNode']:
        """Find an element using its accessibility path"""
        if self.accessibility_path == path:
            return self
        for child in self.children:
            result = child.find_element_by_path(path)
            if result:
                return result
        return None

    def find_elements_by_action(self, action: str) -> List['MacElementNode']:
        """Find all elements that support a specific action"""
        elements = []
        if action in self.actions:
            elements.append(self)
        for child in self.children:
            elements.extend(child.find_elements_by_action(action))
        return elements

    def find_interactive_elements(self) -> List['MacElementNode']:
        """Find all interactive elements in the tree"""
        interactive_elements = []
        if self.is_interactive and self.highlight_index is not None:
            interactive_elements.append(self)
        for child in self.children:
            interactive_elements.extend(child.find_interactive_elements())
        return interactive_elements

    def find_context_elements(self) -> List['MacElementNode']:
        """Find all context elements (non-interactive text elements) in the tree"""
        context_elements = []
        if (self.role in ['AXStaticText', 'AXTextField'] and 
            not self.is_interactive):
            # Only include context elements with meaningful text content
            has_text_content = (
                self.attributes.get('value') or 
                self.attributes.get('title') or 
                self.attributes.get('description')
            )
            if has_text_content:
                context_elements.append(self)
        
        for child in self.children:
            context_elements.extend(child.find_context_elements())
        return context_elements