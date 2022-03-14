# BSD 3-Clause License; see https://github.com/scikit-hep/awkward-1.0/blob/main/LICENSE

import awkward as ak
import ROOT
import base64
import struct

import awkward._v2._lookup  # noqa: E402

cache = {}


class CodeParsingError(Exception):
    """Raised when C++ input code cannot be parsed"""

    pass


class AwkwardArrayDSGenerator:
    @classmethod
    def from_form(cls, form):
        return AwkwardArrayDSGenerator(form.primitive)

    def class_type_suffix(self, key):
        return (
            base64.encodebytes(struct.pack("q", hash(key)))
            .rstrip(b"=\n")
            .replace(b"+", b"")
            .replace(b"/", b"")
            .decode("ascii")
        )

    def class_type(self, key):
        return f"RAwkwardArrayDS_{self.class_type_suffix(self, key)}"

    def generate(self, compiler, array, name=None, use_cached=True):
        layout = array.layout
        generator = ak._v2._connect.cling.togenerator(layout.form)
        # lookup = ak._v2._lookup.Lookup(layout)

        generator.generate(compiler)
        key = generator.entry_type()

        # print(key, self.class_type(self, key))
        # print(generator.dataset(), generator.entry())

        if use_cached:
            out = cache.get("RAwkwardArrayDS")
        else:
            out = None

        # print("RAwkwardArrayDS", ROOT.gROOT.GetClass("RAwkwardArrayDS"))
        # auto array = {generator.dataset()};

        if out is None:
            out = f"""
#include "ROOT/RDataFrame.hxx"
#include "ROOT/RDataSource.hxx"
#include "ROOT/RDF/RInterface.hxx"
#include "ROOT/RDF/Utils.hxx"

namespace ROOT {{
namespace RDF {{

template <typename... ColumnTypes>
class RAwkwardArrayDS final : public ROOT::RDF::RDataSource {{
private:

    using PointerHolderPtrs_t = std::vector<ROOT::Internal::TDS::TPointerHolder *>;

    unsigned int fNSlots{{0U}};
    const PointerHolderPtrs_t fPointerHoldersModels;
    std::vector<PointerHolderPtrs_t> fPointerHolders;
    std::vector<std::pair<ULong64_t, ULong64_t>> fEntryRanges;

    std::vector<ssize_t> fLengths;
    std::vector<ssize_t*> fPtrs;
    std::tuple<ROOT::RVec<ColumnTypes>*...> fColumns;
    const std::vector<std::string> fColNames;
    const std::map<std::string, std::string> fColTypesMap;


    /// type-erased vector of pointers to pointers to column values - one per slot
    Record_t
    GetColumnReadersImpl(std::string_view colName, const std::type_info &id) {{
        auto colNameStr = std::string(colName);
        const auto idName = ROOT::Internal::RDF::TypeID2TypeName(id);
        auto it = fColTypesMap.find(colNameStr);
        if (fColTypesMap.end() == it) {{
            std::string err = "The specified column name, \"" + colNameStr + "\" is not known to the data source.";
            throw std::runtime_error(err);
        }}

        const auto colIdName = it->second;
        if (colIdName != idName) {{
            std::string err = "Column " + colNameStr + " has type " + colIdName +
                              " while the id specified is associated to type " + idName;
            throw std::runtime_error(err);
        }}

        const auto colBegin = fColNames.begin();
        const auto colEnd = fColNames.end();
        const auto namesIt = std::find(colBegin, colEnd, colName);
        const auto index = std::distance(colBegin, namesIt);

        Record_t ret(fNSlots);
        for (auto slot : ROOT::TSeqU(fNSlots)) {{
            ret[slot] = fPointerHolders[index][slot]->GetPointerAddr();
        }}
        return ret;
    }}

    size_t GetEntriesNumber() {{ return std::get<0>(fColumns)->size(); }}

    template <std::size_t... S>
    void SetEntryHelper(unsigned int slot, ULong64_t entry, std::index_sequence<S...>) {{
        std::initializer_list<int> expander {{
            (*static_cast<ColumnTypes *>(fPointerHolders[S][slot]->GetPointer()) = (*std::get<S>(fColumns))[entry], 0)...}};
            (void)expander; // avoid unused variable warnings
    }}

    template <std::size_t... S>
    void ColLenghtChecker(std::index_sequence<S...>) {{
        if (sizeof...(S) < 2)
            return;

        const std::vector<size_t> colLengths {{ std::get<S>(fColumns)->size()...}};
        const auto expectedLen = colLengths[0];
        std::string err;
        for (auto i : ROOT::TSeqI(1, colLengths.size())) {{
            if (expectedLen != colLengths[i]) {{
                err += "Column " + fColNames[i] + " and column " + fColNames[0] +
                   " have different lengths: " + std::to_string(expectedLen) + " and " +
                   std::to_string(colLengths[i]);
            }}
        }}
        if (!err.empty()) {{
            throw std::runtime_error(err);
        }}
    }}

protected:
    std::string AsString() {{
        return "Awkward Array data source";
    }}

public:
    RAwkwardArrayDS(std::pair<std::string, std::pair<ssize_t, ROOT::RVec<ColumnTypes>*>>... colsNameVals)
      : fColumns(std::tuple<ROOT::RVec<ColumnTypes>*...>(colsNameVals.second.second...)),
        fColNames({{colsNameVals.first...}}),
        fColTypesMap({{ {{colsNameVals.first, ROOT::Internal::RDF::TypeID2TypeName(typeid(ColumnTypes))}}...}}),
        fPointerHoldersModels({{new ROOT::Internal::TDS::TTypedPointerHolder<ColumnTypes>(new ColumnTypes())...}}) {{

        std::cout << "Here we are!" << std::endl;
    }}

    RAwkwardArrayDS(std::pair<std::string, ROOT::RVec<ColumnTypes>*>... colsNameVals)
      : fColumns(std::tuple<ROOT::RVec<ColumnTypes>*...>(colsNameVals.second...)),
        fColNames({{colsNameVals.first...}}),
        fColTypesMap({{ {{colsNameVals.first, ROOT::Internal::RDF::TypeID2TypeName(typeid(ColumnTypes))}}...}}),
        fPointerHoldersModels({{new ROOT::Internal::TDS::TTypedPointerHolder<ColumnTypes>(new ColumnTypes())...}}) {{

        std::cout << "Here we are again!" << std::endl;
    }}

    ~RAwkwardArrayDS() {{
    }}

    const std::vector<std::string> &GetColumnNames() const {{ return fColNames; }}

    bool
    HasColumn(std::string_view colName) const {{
        const auto key = std::string(colName);
        const auto endIt = fColTypesMap.end();
        return endIt != fColTypesMap.find(key);
    }}

    std::string
    GetTypeName(std::string_view colName) const {{
        const auto key = std::string(colName);
        return fColTypesMap.at(key);
    }}

    std::vector<std::pair<ULong64_t, ULong64_t>> GetEntryRanges() {{
        auto entryRanges(std::move(fEntryRanges)); // empty fEntryRanges
        return entryRanges;
    }}

    bool SetEntry(unsigned int slot, ULong64_t entry) {{
        SetEntryHelper(slot, entry, std::index_sequence_for<ColumnTypes...>());
        return true;
    }}

    void SetNSlots(unsigned int nSlots) {{
        fNSlots = nSlots;
        const auto nCols = fColNames.size();
        fPointerHolders.resize(nCols); // now we need to fill it with the slots, all of the same type
        auto colIndex = 0U;
        for (auto &&ptrHolderv : fPointerHolders) {{
            for (auto slot : ROOT::TSeqI(fNSlots)) {{
                auto ptrHolder = fPointerHoldersModels[colIndex]->GetDeepCopy();
                ptrHolderv.emplace_back(ptrHolder);
                (void)slot;
            }}
            colIndex++;
        }}
        for (auto &&ptrHolder : fPointerHoldersModels)
            delete ptrHolder;
    }}

    void Initialize() {{
      ColLenghtChecker(std::index_sequence_for<ColumnTypes...>());
      const auto nEntries = GetEntriesNumber();
      const auto nEntriesInRange = nEntries / fNSlots; // between integers. Should make smaller?
      auto reminder = 1U == fNSlots ? 0 : nEntries % fNSlots;
      fEntryRanges.resize(fNSlots);
      auto init = 0ULL;
      auto end = 0ULL;
      for (auto &&range : fEntryRanges) {{
         end = init + nEntriesInRange;
         if (0 != reminder) {{ // Distribute the reminder among the first chunks
            reminder--;
            end += 1;
         }}
         range.first = init;
         range.second = end;
         init = end;
      }}
   }}

    std::string GetLabel() {{ return "{key}"; }}
}};

template <typename... ColumnTypes>
ROOT::RDataFrame* MakeAwkwardDataFrame(std::pair<std::string, ROOT::RVec<ColumnTypes>*> &&... colNameProxyPairs) {{
    return new ROOT::RDataFrame(std::make_unique<RAwkwardArrayDS<ColumnTypes...>>(
      std::forward<std::pair<std::string, ROOT::RVec<ColumnTypes>*>>(colNameProxyPairs)...));
}}

}}
}}
""".strip()
            cache["RAwkwardArrayDS"] = out
            # err = compiler(out)
            # if not err:
            #     raise CodeParsingError("Failed to parse autogenerated code.")

            ROOT.gInterpreter.ProcessLine(out)

        # print(
        #     "generator.dataset",
        #     generator.dataset(),
        #     "generator.entry",
        #     generator.entry(),
        # )


compiler = ROOT.gInterpreter.Declare


def to_rdataframe(columns):
    rdf_columns = {}
    for key in columns:
        layout = columns[key].layout
        generator = ak._v2._connect.cling.togenerator(layout.form)
        # lookup = ak._v2._lookup.Lookup(layout)

        generator.generate(compiler, flatlist_as_rvec=True)
        # g_key = generator.entry_type()

        # print(key, g_key)
        # print(generator.dataset(), generator.entry())
        # err = compiler(
        #     f"""
        #     auto Array_{key}(ssize_t length, ssize_t* ptrs) {{
        #         auto obj = {generator.dataset(flatlist_as_rvec=True)};
        #         return obj;
        #     }}
        #     """
        # )
        # if not err:
        #     raise CodeParsingError("Failed to parse autogenerated code.")

        cpp_code = f"""
auto Array_{key}(ssize_t length, ssize_t* ptrs) {{
    auto obj = {generator.dataset(flatlist_as_rvec=True)};
    return obj;
}}
"""
        ROOT.gInterpreter.ProcessLine(cpp_code)

        # f = getattr(ROOT, f"Array_{key}")(len(layout), lookup.arrayptrs)
        # print(len(layout), lookup.arrayptrs)
        # print(f)

        # rdf_columns[key] = ROOT.RVec[]()# f

    # print(rdf_columns)

    return ROOT.RDF.MakeAwkwardDataFrame(rdf_columns)


# # Let's create some data in numpy arrays
# x = np.array([1, 2, 3], dtype=np.int32)
# y = np.array([4, 5, 6], dtype=np.float64)
#
# # Read the data with RDataFrame
# # The column names in the RDataFrame are defined by the keys of the dictionary.
# # Please note that only fundamental types (int, float, ...) are supported and
# # the arrays must have the same length.
# df = ROOT.RDF.MakeNumpyDataFrame({'x': x, 'y': y})
#
# # You can now use the RDataFrame as usually, e.g. add a column ...
# df = df.Define('z', 'x + y')
#
# # ... or print the content
# df.Display().Print()


def togenerator(form):
    return AwkwardArrayDSGenerator
