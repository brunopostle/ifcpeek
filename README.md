# IfcPeek

An interactive command-line interface to the [IfcOpenShell Selector query syntax](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/selector/index.html) as implemented in [Bonsai BIM](https://bonsaibim.org/). Perfect for BIM professionals who need to explore IFC models and extract data for custom schedules, quantity takeoffs, and reports that aren't available in their BIM software.

**License:** GPLv3

## About IFC Files

IFC (Industry Foundation Classes) files are the open standard for exchanging building information models between different BIM software applications. Unlike proprietary formats, IFC files:

- **Preserve data integrity** across different software platforms
- **Enable vendor-neutral workflows** - no lock-in to specific BIM tools
- **Support long-term archival** with documented, stable format
- **Facilitate collaboration** between disciplines using different software
- **Provide rich semantic data** beyond just geometry - materials, properties, relationships, and metadata

IFC files contain structured building data that often isn't easily accessible through standard BIM software interfaces, making command-line tools like IfcPeek valuable for data analysis and extraction.

## Quick Start

```bash
# Install IfcPeek
pip install ifcopenshell prompt_toolkit
pip install -e .

# Start exploring your model
ifcpeek path/to/your/model.ifc
```

## Why IfcPeek?

- **Explore any IFC model interactively** with intelligent tab completion
- **Extract bulk data** for quantity takeoffs and custom schedules
- **Export to CSV** for analysis in spreadsheet or other tools
- **Discover what's actually in your model** without guessing
- **Format data cleanly** with built-in formatting functions

## Exploring Your Model

### Start with What You Know

When you open a new IFC model, start by typing what you expect to find:

```bash
> IfcW<TAB>
```

Tab completion shows you what's actually available:
```
IfcWall  IfcWindow  IfcWallStandardCase  IfcWallType
```

### See What Instances Exist

Pick an element type and see what's actually in your model:

```bash
> IfcWall
#123=IFCWALL('2O2Fr$t4X7Zf8NOew3FNr2',$,$,'Wall-Exterior-001',...);
#156=IFCWALL('3P3Gs$u5Y8Ag9OPfx4GOr3',$,$,'Wall-Interior-002',...);
...
```

The output shows you all wall instances in SPF format (Step Physical File - the native IFC format). Each line represents one wall with its unique ID and properties.

### Filter Down to What You Need

Now filter to find specific walls using tab completion to discover available options:

```bash
> IfcWall, <TAB>
```

You'll see filtering options like:
```
Name  material  type  location  Pset_WallCommon  classification
```

#### Filter by Location
```bash
> IfcWall, location="Level 3"
```

#### Filter by Material
```bash
> IfcWall, material=concrete
```

#### Filter by Properties
Property sets (Psets) contain standardized IFC properties:
```bash
> IfcWall, Pset_WallCommon.FireRating=2HR
```

#### Combine Multiple Filters
```bash
> IfcWall, location="Level 3", material=concrete, Pset_WallCommon.LoadBearing=TRUE
```

**Pro Tip:** Use `--debug` mode to see exactly how your filters are being processed:
```bash
ifcpeek --debug model.ifc
```

## Extracting Data for Analysis

### Basic Value Extraction

Once you've filtered to the elements you want, extract specific data using a semicolon:

```bash
> IfcWall, material=concrete ; Name
Wall-Exterior-001
Wall-Exterior-003
Wall-Interior-012
```

### Multiple Values (CSV Output)

Extract multiple properties for quantity takeoffs or schedules:

```bash
> IfcWall, location="Level 3" ; Name ; type.Name ; Qto_WallBaseQuantities.NetArea
Wall-Ext-01    WT-Exterior-200mm    24.5
Wall-Int-02    WT-Interior-100mm    18.2
Wall-Int-03    WT-Interior-150mm    31.8
```

The output is tab-separated, which Excel and other tools recognize as CSV.

### CSV Headers for Spreadsheet Import

Enable headers mode to include column names in your CSV output:

```bash
# Toggle headers in interactive mode
> /headers
Headers mode enabled.

> IfcWall ; Name ; type.Name ; Qto_WallBaseQuantities.NetArea
Name	type.Name	Qto_WallBaseQuantities.NetArea
Wall-Ext-01    WT-Exterior-200mm    24.5
Wall-Int-02    WT-Interior-100mm    18.2
```

Or use the `--headers` command-line flag for piped input:

```bash
# Include headers when piping to CSV files
echo 'IfcWall ; Name ; type.Name ; Qto_WallBaseQuantities.NetArea' | ifcpeek --headers model.ifc > walls.csv
```

### Discover Available Properties

Use tab completion after the semicolon to see what you can extract:

```bash
> IfcWall ; <TAB>
```

Shows context-aware suggestions based on your filter:
```
Name  Description  type  material  Pset_WallCommon  Qto_WallBaseQuantities
```

#### Navigate Property Hierarchies
```bash
> IfcWall ; type.<TAB>
Name  Description  Width  Height
```

```bash
> IfcWall ; material.<TAB>
Name  Category  item
```

```bash
> IfcWall ; Pset_WallCommon.<TAB>
FireRating  LoadBearing  Status  ThermalTransmittance
```

### Format Your Data

Clean up extracted values with formatting functions (similar to spreadsheet formulas):

#### Standardize Text
```bash
> IfcWall ; upper(Name) ; type.Name
WALL-EXTERIOR-001    WT-Exterior-200mm
WALL-INTERIOR-002    WT-Interior-100mm
```

#### Round Numbers
```bash
> IfcWall ; Name ; round(Qto_WallBaseQuantities.NetArea, 0.1)
Wall-Ext-01    24.5
Wall-Int-02    18.2
```

#### Combine Values
```bash
> IfcWall ; concat(Name, " - ", type.Name)
Wall-Ext-01 - WT-Exterior-200mm
Wall-Int-02 - WT-Interior-100mm
```

#### More Formatting Functions
Available functions include: `upper()`, `lower()`, `title()`, `concat()`, `round()`, `int()`, `number()`, `metric_length()`, `imperial_length()`. See the [IfcOpenShell selector documentation](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/selector/index.html) for complete details.

## Common BIM Workflows

### Quantity Takeoff by Material

```bash
# Find all concrete elements and get quantities
> IfcWall, IfcSlab, material=concrete ; Name ; type.Name ; /Qto_.*Quantities/.NetVolume

# Export to file for spreadsheet analysis with headers
echo 'IfcWall, IfcSlab, material=concrete ; Name ; type.Name ; /Qto_.*Quantities/.NetVolume' | ifcpeek --headers model.ifc > concrete_quantities.csv
```

### Fire Rating Schedule

```bash
# All fire-rated elements with ratings and locations
> IfcElement, /Pset_.*Common/.FireRating != NULL ; Name ; storey.Name ; /Pset_.*Common/.FireRating
```

### MEP Equipment Schedule

```bash
# HVAC equipment with specifications
> IfcFlowTerminal ; Name ; type.Name ; Pset_FlowTerminalCommon.NominalAirFlowRate
```

### Custom Property Analysis

```bash
# Elements with custom manufacturer data (note the two regular expressions separated by a . in the query)
> IfcElement, /Pset_Manufacturer.*/./.*/ != NULL ; Name ; type.Name ; /Pset_Manufacturer.*/
```

## Production Use

### Pipe Queries from Scripts

For repeated analysis, save queries to files and pipe them:

```bash
# queries.txt contains your extraction queries
ifcpeek --headers model.ifc < queries.txt > results.csv
```

### Batch Processing

```bash
# Process multiple models
for model in *.ifc; do
  echo "Processing $model..."
  echo 'IfcWall ; Name ; Qto_WallBaseQuantities.NetArea' | ifcpeek --headers "$model" > "${model%.ifc}_walls.csv"
done
```

## Advanced Features

### Complex Filtering

#### Multiple Element Types
```bash
> IfcWall, IfcSlab, IfcColumn ; Name ; material.Name
```

#### Union Queries
```bash
> IfcWall, material=concrete + IfcSlab, material=steel
```

#### Negation
```bash
> IfcWall, ! material=gypsum  # All walls except gypsum
```

#### Regular Expressions
```bash
> IfcDoor, Name=/D[0-9]{2}/  # Doors named D01, D02, etc.
```

### Spatial Queries

Location queries work hierarchically - if an element is in a space, and that space is on Level 3, then `location="Level 3"` will find it:

```bash
> IfcPump, location="Level 3"  # Finds pumps in spaces on Level 3
```

### Debugging and Troubleshooting

#### Debug Mode
```bash
ifcpeek --debug model.ifc
```
Shows detailed processing information and cache building progress.

#### Verbose Startup
```bash
ifcpeek --verbose model.ifc
```
Shows model loading details and completion system status.

#### Error Details
When value extraction fails, detailed errors appear in stderr while keeping stdout clean for CSV output:
```bash
> IfcWall ; NonExistentProperty
Property 'NonExistentProperty' not found on entity #123
```

### Interactive Features

#### Command History
- **Up/Down arrows**: Navigate previous queries
- **Ctrl-R**: Search command history
- **History persistence**: Saved in `~/.local/state/ifcpeek/history`

#### Built-in Commands
- `/help` - Show complete help
- `/exit` or `/quit` - Exit shell
- `/debug` - Toggle debug mode during session
- `/headers` - Toggle CSV headers mode during session
- `Ctrl-D` - Exit shell

## Installation & Requirements

### Requirements
- Python 3.10+
- IfcOpenShell 0.8.0+
- prompt_toolkit 3.0.0+

### Installation

#### From Source
```bash
git clone https://github.com/brunopostle/ifcpeek.git
cd ifcpeek
pip install -e .
```

#### Dependencies Only
```bash
pip install ifcopenshell prompt_toolkit
```

### Platform Support
- Linux, macOS, Windows
- Terminal/Command Prompt with UTF-8 support
- Supports both interactive and non-interactive (piped) usage

## Tips for BIM Professionals

### Model Discovery Strategy
1. **Start broad**: `IfcElement` to see all element types present
2. **Focus by discipline**: `IfcWall`, `IfcFlowTerminal`, `IfcStructuralMember`
3. **Check spatial structure**: `IfcBuildingStorey`, `IfcSpace`
4. **Explore property sets**: Use tab completion to find `Pset_` and `Qto_` properties

### Common Gotchas
- **Property names are case-sensitive**: `FireRating` not `firerating`
- **Quoted values for spaces**: `location="Level 3"` not `location=Level 3`
- **Property sets vary by model**: Use tab completion to see what's actually available
- **Empty results are silent**: If no output appears, your filter didn't match anything

### Performance with Large Models
- **Filter first**: Always use specific filters before value extraction
- **Batch similar queries**: Multiple value extractions in one query is faster than separate queries
- **Use debug mode**: Monitor performance with `--debug` for complex queries

## Query Syntax Reference

### Filter Syntax (Before Semicolon)
This follows [IfcOpenShell selector syntax](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/selector/index.html):

```bash
# Element classes
IfcWall, IfcSlab, IfcColumn

# Attributes
IfcWall, Name=Wall-01
IfcDoor, PredefinedType=DOOR

# Properties
IfcWall, Pset_WallCommon.FireRating=2HR

# Keywords
IfcWall, material=concrete
IfcElement, location="Level 3"
IfcWall, type=WT-200mm

# Comparisons (note that numbers with . need to be quoted)
IfcSlab, Qto_SlabBaseQuantities.NetArea > "100.0"
IfcWall, Name != "Wall-01"
IfcElement, Name *= "Fire"  # Contains "Fire"

# Regular expressions
IfcDoor, Name=/D[0-9]{2}/
IfcElement, /Pset_.*Common/.* != NULL

# Combinations
IfcWall, location="Level 3", material=concrete, Pset_WallCommon.LoadBearing=TRUE

# Union (OR)
IfcWall, material=concrete + IfcSlab, material=steel

# Negation
IfcWall, ! material=gypsum
IfcElement, ! IfcWall  # All elements except walls
```

### Value Extraction Syntax (After Semicolon)
This follows [IfcOpenShell value extraction syntax](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/selector/index.html):

```bash
# Basic attributes
Name, Description, GlobalId

# Type relationships
type.Name, type.Description

# Spatial relationships
storey.Name, building.Name, space.Name

# Materials
material.Name, material.Category
material.item.0.Name  # First material in set

# Property sets
Pset_WallCommon.FireRating
/Pset_.*Common/.Status  # Any common property set

# Quantity sets
Qto_WallBaseQuantities.NetArea
Qto_WallBaseQuantities.NetVolume

# Coordinates
x, y, z  # Local coordinates
easting, northing, elevation  # Map coordinates

# Counts and lists
types.count  # Number of type occurrences
materials.count  # Number of materials
```

## Troubleshooting

### Model Won't Load
```bash
# Check file validity
ifcpeek --verbose model.ifc

# Common issues:
# - File path incorrect
# - File corrupted
# - Insufficient memory for large models
# - File permissions
```

### No Results from Query
```bash
# Enable debug mode to see what's happening
ifcpeek --debug model.ifc
> IfcWall  # Check if any walls exist first
> IfcElement  # Check what element types are available
```

### Tab Completion Not Working
```bash
# Check if running in proper terminal
# Ensure prompt_toolkit is installed
pip show prompt_toolkit

# Try force interactive mode for testing
ifcpeek --force-interactive model.ifc
```

### Slow Performance
```bash
# Use more specific filters
> IfcWall, location="Level 3"  # Better than just IfcWall

# Monitor with debug mode
ifcpeek --debug model.ifc
```

## Support & Contributing

### Getting Help
- **Built-in help**: Type `/help` in the shell
- **Documentation**: [IfcOpenShell Selector Docs](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/selector/index.html)
- **Community support**: [OSArch Community Forum](https://community.osarch.org/)
- **Issues**: [GitHub Issues](https://github.com/brunopostle/ifcpeek/issues)

### Reporting Issues
Include:
1. Full error message and traceback
2. IFC file details (size, schema version, source software)
3. Exact query that failed
4. Python and dependency versions
5. Operating system

### Development
```bash
# Development setup
git clone https://github.com/brunopostle/ifcpeek.git
cd ifcpeek
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v
```

## Development Notes

**IfcPeek** is an experimental application developed using LLM-assisted code generation. While functional and tested, this development approach may introduce:

- **Subtle logic errors** in edge cases not covered by tests
- **Inconsistent error handling** patterns across different code paths
- **Performance inefficiencies** from non-optimal algorithmic choices
- **Documentation gaps** where generated code lacks human domain expertise
- **Integration issues** between LLM-generated modules

Users should validate results for critical applications and report any unexpected behavior.

---

**IfcPeek** - Explore, filter, and extract data from any IFC model.
